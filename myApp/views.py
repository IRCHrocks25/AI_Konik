import csv
import importlib
import io
import json as _json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone as dj_tz
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt

from .admin_audit import log_error, record_admin_action
from .auth_utils import (
    _do_restore_impersonation,
    _is_admin_user,
    admin_required,
    check_impersonation_timeout,
    get_current_user,
    get_request_json,
    login_required_api,
    login_user,
    logout_user,
)
from .models import Agent, AgentPrompt, ChatMessage, ChatSession, CustomUser, ErrorLog, Prompt, SavedPrompt
from .openai_service import (
    MAX_REQUEST_TOKENS,
    estimate_messages_tokens,
    get_openai_reply,
    trim_history_to_budget,
)
from .personalization import build_full_system_prompt
from .seed_data import seed_agents_and_prompts

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover - optional dependency runtime check
    load_workbook = None

try:
    import cloudinary
    import cloudinary.uploader
except Exception:  # pragma: no cover - optional dependency runtime check
    cloudinary = None

logger = logging.getLogger(__name__)

SEED_PROMPTS = [
    {
        "title": "Review this NDA for liability exposure",
        "body": "Analyze this NDA and identify liability risks, indemnification issues, and missing protections.",
        "industry": "legal",
        "category": "Contracts",
        "usage_count": 2100,
    },
    {
        "title": "Generate a mutual NDA for software development",
        "body": "Create a mutual NDA for software collaboration with IP protections and a two-year confidentiality period.",
        "industry": "legal",
        "category": "Drafting",
        "usage_count": 1800,
    },
    {
        "title": "Summarize key risks in M&A term sheet",
        "body": "Review this term sheet and summarize top seller-side risks and unusual clauses.",
        "industry": "legal",
        "category": "M&A",
        "usage_count": 1400,
    },
]

INDUSTRY_MAP = {
    "legal": "legal",
    "healthcare": "healthcare",
    "finance": "finance",
    "marketing": "marketing",
    "technology": "technology",
    "real estate": "realestate",
    "realestate": "realestate",
    "accounting": "accounting",
    "logistics": "logistics",
    "manufacturing": "manufacturing",
}

_PROFILE_CHOICES = {
    "company_size": {"solo", "2-10", "11-50", "51-200", "200+"},
    "years_experience": {"<1", "1-3", "3-7", "7-15", "15+"},
    "communication_style": {"direct", "friendly", "formal", "casual"},
    "response_length": {"concise", "balanced", "detailed"},
    "expertise_level": {"beginner", "intermediate", "expert"},
    "emoji_use": {"never", "sparingly", "freely"},
    "pushback_style": {"always", "diplomatic", "supportive"},
    "explanation_style": {"answer_only", "with_reasoning", "step_by_step"},
    "clarifying_questions": {"when_needed", "always", "never"},
}

_PROFILE_TEXT_LIMITS = {
    "display_name": 80,
    "role": 120,
    "timezone": 64,
    "current_focus": 500,
    "things_to_avoid": 300,
    "about_me": 1000,
}

_EXPERTISE_AREAS_VALID = {
    "Legal", "Finance", "Marketing", "Tech", "Healthcare", "RealEstate",
    "Accounting", "Logistics", "Manufacturing", "Operations", "Sales",
    "HR", "Strategy", "Product", "Design",
}

HEADER_ALIASES = {
    "id": "id",
    "industry": "industry",
    "category": "category",
    "subcategory": "sub_category",
    "subcategory": "sub_category",
    "sub-category": "sub_category",
    "prompttitle": "prompt_title",
    "prompt title": "prompt_title",
    "promptfulltext": "prompt_full_text",
    "prompt(fulltext)": "prompt_full_text",
    "prompt (full text)": "prompt_full_text",
    "difficulty": "difficulty",
    "usecasetype": "use_case_type",
    "use case type": "use_case_type",
    "estimatedtimesaved": "estimated_time_saved",
    "estimated time saved": "estimated_time_saved",
    "tags": "tags",
}

LEGACY_PATH_REDIRECTS = {
    "index.html": "/index/",
    "dashboard.html": "/dashboard/",
    "agents.html": "/agents/",
    "agent-chat.html": "/agent-chat/",
    "prompts.html": "/prompts/",
    "industries.html": "/industries/",
    "events.html": "/events/",
    "tools.html": "/tools/",
    "consulting.html": "/consulting/",
    "billing.html": "/billing/",
    "profile.html": "/profile/",
    "settings.html": "/settings/",
    "login.html": "/login/",
    "register.html": "/register/",
    "prompt-import.html": "/prompt-import/",
    "agent-admin.html": "/agent-admin/",
}


def ensure_seed_prompts():
    if Prompt.objects.exists():
        return
    Prompt.objects.bulk_create([Prompt(**prompt) for prompt in SEED_PROMPTS])


def ensure_seed_agents():
    seed_agents_and_prompts()


def home(request):
    return render(request, "index.html")


def dashboard(request):
    return render(request, "dashboard.html")


def agents(request):
    return render(request, "agents.html")


def agent_chat(request):
    return render(request, "agent-chat.html")


def prompts(request):
    return render(request, "prompts.html")


def industries(request):
    return render(request, "industries.html")


def events(request):
    return render(request, "events.html")


def tools(request):
    return render(request, "tools.html")


def consulting(request):
    return render(request, "consulting.html")


def billing(request):
    return render(request, "billing.html")


def profile_page(request):
    return render(request, "profile.html")


def settings_page(request):
    return render(request, "settings.html")


def login(request):
    return render(request, "login.html")


def register(request):
    return render(request, "register.html")


def shared_css(request):
    return render(request, "shared.css", content_type="text/css")


def legacy_html_redirect(request, page):
    target = LEGACY_PATH_REDIRECTS.get(page)
    if not target:
        raise Http404("Legacy path not found")
    query = request.META.get("QUERY_STRING", "")
    if query:
        return redirect(f"{target}?{query}")
    return redirect(target)


@admin_required
def admin_dashboard(request, **kwargs):
    return render(request, "admin-dashboard.html")


def prompt_import_dashboard(request):
    user = get_current_user(request)
    if not user:
        return redirect("login")
    if not _is_admin_user(user):
        return redirect("prompts")
    return render(request, "prompt-import.html")


def agent_admin_dashboard(request):
    user = get_current_user(request)
    if not user:
        return redirect("login")
    if not _is_admin_user(user):
        return redirect("agents")
    return render(request, "agent-admin.html")


@csrf_exempt
def api_register(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    first_name = str(payload.get("first_name", "")).strip()
    last_name = str(payload.get("last_name", "")).strip()
    industry = str(payload.get("industry", "")).strip()

    if not email or not password or not first_name:
        return JsonResponse(
            {"error": "first_name, email, and password are required"}, status=400
        )
    if CustomUser.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=409)

    user = CustomUser.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=email,
        industry=industry,
        password_hash=make_password(password),
    )
    login_user(request, user)
    return JsonResponse(
        {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "industry": user.industry,
        },
        status=201,
    )


@csrf_exempt
def api_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    user = CustomUser.objects.filter(email=email).first()
    if not user or not check_password(password, user.password_hash):
        # Bridge Django auth users (including superusers) into CustomUser login.
        django_user_model = get_user_model()
        django_user = django_user_model.objects.filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        ).first()
        if not django_user or not django_user.check_password(password):
            return JsonResponse({"error": "Invalid email or password"}, status=401)

        bridge_email = (django_user.email or "").strip().lower()
        if not bridge_email:
            # Ensure a valid email for CustomUser unique field.
            bridge_email = f"{django_user.username}@local.user"

        user, _ = CustomUser.objects.get_or_create(
            email=bridge_email,
            defaults={
                "first_name": django_user.first_name or django_user.username or "User",
                "last_name": django_user.last_name or "",
                "industry": "",
                "password_hash": django_user.password,
            },
        )
        # Keep the bridge record synced to Django auth credentials.
        fields_to_update = []
        desired_first = django_user.first_name or django_user.username or "User"
        desired_last = django_user.last_name or ""
        if user.first_name != desired_first:
            user.first_name = desired_first
            fields_to_update.append("first_name")
        if user.last_name != desired_last:
            user.last_name = desired_last
            fields_to_update.append("last_name")
        if user.password_hash != django_user.password:
            user.password_hash = django_user.password
            fields_to_update.append("password_hash")
        if fields_to_update:
            user.save(update_fields=fields_to_update)

    login_user(request, user)
    return JsonResponse(
        {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "industry": user.industry,
        }
    )


@csrf_exempt
def api_logout(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    logout_user(request)
    return JsonResponse({"success": True})


def api_me(request):
    check_impersonation_timeout(request)  # must run before get_current_user reads the session
    user = get_current_user(request)
    if not user:
        return JsonResponse({"authenticated": False, "is_admin": False})
    is_impersonating = "_impersonated_by" in request.session
    result = {
        "authenticated": True,
        "is_admin": _is_admin_user(user),
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "industry": user.industry,
        "is_impersonating": is_impersonating,
    }
    if is_impersonating:
        admin_id = request.session.get("_impersonated_by")
        admin_custom = CustomUser.objects.filter(id=admin_id).first()
        result["impersonated_by_email"] = admin_custom.email if admin_custom else None
    return JsonResponse(result)


def _validate_and_build_profile_updates(payload):
    """Validate a profile payload and return (updates, errors).

    updates: dict of field → validated value, ready to setattr on a CustomUser.
    errors:  dict of field → error message for invalid inputs.

    Handles all 18 personalization fields. is_suspended is intentionally NOT
    handled here — callers that need it validate and append it themselves so
    that admin-specific business rules (cannot suspend self/other-admin) stay
    in the view layer, not in this shared helper.
    """
    errors, updates = {}, {}

    for field, limit in _PROFILE_TEXT_LIMITS.items():
        if field not in payload:
            continue
        val = str(payload[field]).strip()
        if len(val) > limit:
            errors[field] = f"Too long (max {limit} characters)."
        else:
            updates[field] = val

    for field, valid_set in _PROFILE_CHOICES.items():
        if field not in payload:
            continue
        val = str(payload[field]).strip()
        if val and val not in valid_set:
            errors[field] = f"Invalid choice. Allowed: {', '.join(sorted(valid_set))}."
        else:
            updates[field] = val

    if "industry" in payload:
        updates["industry"] = _normalize_industry(str(payload.get("industry", "")))

    if "formality" in payload:
        try:
            v = int(payload["formality"])
            if not 1 <= v <= 5:
                raise ValueError
            updates["formality"] = v
        except (TypeError, ValueError):
            errors["formality"] = "Must be an integer between 1 and 5."

    if "expertise_areas" in payload:
        val = payload["expertise_areas"]
        if not isinstance(val, list):
            errors["expertise_areas"] = "Must be a list."
        else:
            invalid = [v for v in val if v not in _EXPERTISE_AREAS_VALID]
            if invalid:
                errors["expertise_areas"] = f"Invalid values: {', '.join(sorted(invalid))}."
            else:
                updates["expertise_areas"] = val

    return updates, errors


@csrf_exempt
@login_required_api
def api_profile(request):
    user = request.current_user

    if request.method == "GET":
        return JsonResponse({
            "display_name": user.display_name,
            "role": user.role,
            "industry": user.industry,
            "company_size": user.company_size,
            "years_experience": user.years_experience,
            "timezone": user.timezone,
            "communication_style": user.communication_style,
            "response_length": user.response_length,
            "expertise_level": user.expertise_level,
            "formality": user.formality,
            "emoji_use": user.emoji_use,
            "pushback_style": user.pushback_style,
            "explanation_style": user.explanation_style,
            "clarifying_questions": user.clarifying_questions,
            "expertise_areas": user.expertise_areas,
            "current_focus": user.current_focus,
            "things_to_avoid": user.things_to_avoid,
            "about_me": user.about_me,
        })

    if request.method != "PUT":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    updates, errors = _validate_and_build_profile_updates(payload)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    if not updates:
        return JsonResponse({"success": True})

    fields_to_save = list(updates.keys())

    if user.profile_completed_at is None:
        has_meaningful = any(
            (isinstance(v, list) and v) or (isinstance(v, str) and v)
            for v in updates.values()
        )
        if has_meaningful:
            user.profile_completed_at = dj_tz.now()
            fields_to_save.append("profile_completed_at")

    for field, value in updates.items():
        setattr(user, field, value)

    fields_to_save.append("updated_at")
    user.save(update_fields=fields_to_save)
    return JsonResponse({"success": True})


_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def _is_valid_hex_color(value):
    """True iff value is a hex color: #RGB, #RGBA, #RRGGBB, or #RRGGBBAA.

    Hex-only validation defends against stored XSS via the accent_bg field —
    rejecting anything that could end up in a style attribute or CSS custom
    property as raw user input.
    """
    return bool(_HEX_COLOR_RE.match(str(value or "").strip()))


def _serialize_agent(agent, include_prompts=False):
    data = {
        "id": agent.id,
        "name": agent.name,
        "slug": agent.slug,
        "industry": agent.industry,
        "description": agent.description,
        "icon_class": agent.icon_class,
        "accent_bg": agent.accent_bg,
        "tag": agent.tag,
        "usage_count": agent.usage_count,
        "is_featured": agent.is_featured,
        "is_active": agent.is_active,
        "sort_order": agent.sort_order,
    }
    if include_prompts:
        prompts = list(agent.prompts.all().values("id", "prompt_type", "content", "sort_order"))
        data["hints"] = [p["content"] for p in prompts if p["prompt_type"] == "hint"]
        data["use_cases"] = [p["content"] for p in prompts if p["prompt_type"] == "use_case"]
        data["prompts"] = prompts
    return data


def _to_non_negative_int(value, default=0):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def api_agents(request):
    ensure_seed_agents()
    include_prompts = request.GET.get("include_prompts", "").strip() == "1"
    industry = request.GET.get("industry", "").strip().lower()
    queryset = Agent.objects.filter(is_active=True)
    if industry and industry != "all":
        queryset = queryset.filter(industry__iexact=industry)
    return JsonResponse(
        {
            "items": [
                _serialize_agent(agent, include_prompts=include_prompts)
                for agent in queryset.prefetch_related("prompts")
            ]
        }
    )


@csrf_exempt
@login_required_api
def api_admin_agents(request):
    ensure_seed_agents()
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    if request.method == "GET":
        queryset = Agent.objects.all().prefetch_related("prompts")
        return JsonResponse({"items": [_serialize_agent(agent, include_prompts=True) for agent in queryset]})

    if request.method == "POST":
        payload = get_request_json(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        name = str(payload.get("name", "")).strip()
        industry = str(payload.get("industry", "")).strip().lower()
        description = str(payload.get("description", "")).strip()
        errors = {}
        if not name:
            errors['name'] = 'Required.'
        if not industry:
            errors['industry'] = 'Required.'
        if not description:
            errors['description'] = 'Required.'
        if errors:
            return JsonResponse({'errors': errors}, status=400)
        slug = slugify(name)
        if not slug:
            return JsonResponse({"error": "Invalid name"}, status=400)
        if Agent.objects.filter(Q(name__iexact=name) | Q(slug=slug)).exists():
            return JsonResponse({"error": "Agent already exists"}, status=409)

        accent_bg = str(payload.get("accent_bg", "#EEF2FF")).strip() or "#EEF2FF"
        if not _is_valid_hex_color(accent_bg):
            return JsonResponse({"error": "accent_bg must be a hex color like #RRGGBB"}, status=400)

        # hints / use_cases are optional on POST. Old /agent-admin/ flow omits them
        # and creates AgentPrompts via the separate /api/admin/agents/<id>/prompts
        # endpoint instead — that path is preserved. New admin-dashboard flow
        # supplies both arrays here so creation is one round-trip.
        raw_hints = payload.get("hints") or []
        raw_use_cases = payload.get("use_cases") or []
        if not isinstance(raw_hints, list) or not isinstance(raw_use_cases, list):
            return JsonResponse({"error": "hints and use_cases must be arrays"}, status=400)
        hints = [str(h).strip() for h in raw_hints if str(h).strip()][:8]
        use_cases = [str(u).strip() for u in raw_use_cases if str(u).strip()][:8]

        with transaction.atomic():
            agent = Agent.objects.create(
                name=name,
                slug=slug,
                industry=industry,
                description=description,
                icon_class=str(payload.get("icon_class", "fa-robot")).strip() or "fa-robot",
                accent_bg=accent_bg,
                tag=str(payload.get("tag", "")).strip(),
                usage_count=_to_non_negative_int(payload.get("usage_count", 0), default=0),
                is_featured=bool(payload.get("is_featured", False)),
                is_active=bool(payload.get("is_active", True)),
                sort_order=_to_non_negative_int(payload.get("sort_order", 100), default=100),
            )
            AgentPrompt.objects.bulk_create(
                [
                    AgentPrompt(agent=agent, prompt_type="hint", content=h, sort_order=(i + 1) * 10)
                    for i, h in enumerate(hints)
                ]
                + [
                    AgentPrompt(agent=agent, prompt_type="use_case", content=u, sort_order=(i + 1) * 10)
                    for i, u in enumerate(use_cases)
                ]
            )

        record_admin_action(
            admin=request.current_user,
            action_type="agent.create",
            target_type="agent",
            target_id=agent.id,
            metadata={
                "name": agent.name,
                "industry": agent.industry,
                "hints_count": len(hints),
                "use_cases_count": len(use_cases),
            },
        )
        return JsonResponse(_serialize_agent(agent, include_prompts=True), status=201)

    return JsonResponse({"error": "Method not allowed"}, status=405)


# Field → max-length cap for PATCH text updates. industry/description checked
# at save time the same way as POST. Caps are generous; UI enforces tighter
# practical limits.
_AGENT_PATCH_TEXT_FIELDS = {
    "name": 160,
    "industry": 100,
    "description": 4000,
    "tag": 120,
    "icon_class": 80,
}


@csrf_exempt
@login_required_api
def api_admin_agent_detail(request, agent_id):
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)
    agent = Agent.objects.filter(id=agent_id).first()
    if not agent:
        return JsonResponse({"error": "Agent not found"}, status=404)

    if request.method == "DELETE":
        agent_name = agent.name
        prompts_count = agent.prompts.count()
        agent.delete()  # FK CASCADE removes AgentPrompt rows
        record_admin_action(
            admin=request.current_user,
            action_type="agent.delete",
            target_type="agent",
            target_id=agent_id,
            metadata={"name": agent_name, "prompts_deleted": prompts_count},
        )
        return JsonResponse({"deleted": True})

    if request.method == "PATCH":
        payload = get_request_json(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)

        errors = {}
        updates = {}

        for field, limit in _AGENT_PATCH_TEXT_FIELDS.items():
            if field not in payload:
                continue
            val = str(payload[field]).strip()
            if field in ("name", "industry", "description") and not val:
                errors[field] = "Cannot be empty."
                continue
            if len(val) > limit:
                errors[field] = f"Too long (max {limit})."
                continue
            if field == "industry":
                val = val.lower()
            updates[field] = val

        # Re-slug when name changes; reject collisions with other agents.
        if "name" in updates and updates["name"] != agent.name:
            new_slug = slugify(updates["name"])
            if not new_slug:
                errors["name"] = "Invalid name."
            elif Agent.objects.filter(
                Q(name__iexact=updates["name"]) | Q(slug=new_slug)
            ).exclude(id=agent.id).exists():
                errors["name"] = "Another agent with this name already exists."
            else:
                updates["slug"] = new_slug

        if "accent_bg" in payload:
            val = str(payload["accent_bg"]).strip()
            if not _is_valid_hex_color(val):
                errors["accent_bg"] = "Must be a hex color like #RRGGBB."
            else:
                updates["accent_bg"] = val

        for bool_field in ("is_featured", "is_active"):
            if bool_field in payload:
                if not isinstance(payload[bool_field], bool):
                    errors[bool_field] = "Must be a boolean."
                else:
                    updates[bool_field] = payload[bool_field]

        for int_field in ("usage_count", "sort_order"):
            if int_field in payload:
                updates[int_field] = _to_non_negative_int(
                    payload[int_field], default=getattr(agent, int_field)
                )

        replace_hints = "hints" in payload
        replace_use_cases = "use_cases" in payload
        new_hints = []
        new_use_cases = []
        if replace_hints:
            if not isinstance(payload["hints"], list):
                errors["hints"] = "Must be an array."
            else:
                new_hints = [str(h).strip() for h in payload["hints"] if str(h).strip()][:8]
        if replace_use_cases:
            if not isinstance(payload["use_cases"], list):
                errors["use_cases"] = "Must be an array."
            else:
                new_use_cases = [str(u).strip() for u in payload["use_cases"] if str(u).strip()][:8]

        if errors:
            return JsonResponse({"errors": errors}, status=400)

        changed_fields = list(updates.keys())
        with transaction.atomic():
            if updates:
                for field, value in updates.items():
                    setattr(agent, field, value)
                agent.save(update_fields=changed_fields + ["updated_at"])
            if replace_hints:
                agent.prompts.filter(prompt_type="hint").delete()
                AgentPrompt.objects.bulk_create([
                    AgentPrompt(agent=agent, prompt_type="hint", content=h, sort_order=(i + 1) * 10)
                    for i, h in enumerate(new_hints)
                ])
                changed_fields.append("hints")
            if replace_use_cases:
                agent.prompts.filter(prompt_type="use_case").delete()
                AgentPrompt.objects.bulk_create([
                    AgentPrompt(agent=agent, prompt_type="use_case", content=u, sort_order=(i + 1) * 10)
                    for i, u in enumerate(new_use_cases)
                ])
                changed_fields.append("use_cases")

        record_admin_action(
            admin=request.current_user,
            action_type="agent.update",
            target_type="agent",
            target_id=agent.id,
            metadata={"changed_fields": changed_fields},
        )
        agent.refresh_from_db()
        return JsonResponse(_serialize_agent(agent, include_prompts=True))

    return JsonResponse({"error": "Method not allowed"}, status=405)


# Fixed prompt template for agent AI generation. Single user message — no
# system prompt — because this is one-shot structured generation, not a chat.
# Curly braces around the JSON example are doubled so str.format leaves them
# untouched. Token cost: ~250 prompt + ~400 response ≈ 650 per call.
_AGENT_GENERATION_PROMPT_TEMPLATE = """You are configuring a new AI agent for AI KONIK, a business assistant platform.

Agent details:
- Name: {name}
- Industry: {industry}
- Description: {description}
- Tag: {tag}

Generate suggestions in valid JSON. Strict requirements:

1. "hints" — array of EXACTLY 4 short example user queries (5-12 words each, imperative voice). These appear as quick-start buttons in the chat UI.

2. "use_cases" — array of EXACTLY 4 longer example requests (15-30 words each, more detailed than hints). These appear as previewable examples.

3. "accent_bg" — exactly one hex color in #RRGGBB format. Choose a soft pastel that fits the industry's emotional register:
   - legal/finance → cool blues like #EEF2FF
   - healthcare → gentle greens like #ECFDF5
   - marketing/design → warm pinks like #FFF1F2
   - technology → light blues like #F0F9FF
   - real estate → light violets like #F5F3FF
   - accounting → mint greens like #ECFDF5
   - logistics/manufacturing → warm neutrals like #FFF7ED or #F8FAFC
   - other → fall back to a neutral cool tone like #F1F5F9

Return ONLY this JSON structure, with NO markdown fences and NO explanation:

{{
  "hints": ["...", "...", "...", "..."],
  "use_cases": ["...", "...", "...", "..."],
  "accent_bg": "#XXXXXX"
}}"""


@csrf_exempt
@login_required_api
def api_admin_agent_generate(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    name = str(payload.get("name", "")).strip()
    industry = str(payload.get("industry", "")).strip()
    description = str(payload.get("description", "")).strip()
    tag = str(payload.get("tag", "")).strip()

    if not name or not industry or not description:
        return JsonResponse(
            {"error": "name, industry, and description are required"}, status=400
        )
    if len(name) > 200:
        return JsonResponse({"error": "name must be ≤200 characters"}, status=400)
    if len(description) > 1000:
        return JsonResponse({"error": "description must be ≤1000 characters"}, status=400)

    prompt_text = _AGENT_GENERATION_PROMPT_TEMPLATE.format(
        name=name, industry=industry, description=description, tag=tag or "(none)",
    )

    # Audit the attempt before calling OpenAI so failures are still recorded.
    record_admin_action(
        admin=request.current_user,
        action_type="agent.generate",
        target_type="agent",
        metadata={"name_input": name, "industry_input": industry},
    )

    try:
        raw_text, _ = get_openai_reply([{"role": "user", "content": prompt_text}])
    except Exception as exc:
        logger.exception("Agent generate failed: %s", exc)
        log_error(
            error_type="openai_agent_generate",
            message=str(exc),
            user=request.current_user,
            metadata={"name_input": name},
        )
        return JsonResponse({"error": "Generation failed. Please try again."}, status=502)

    cleaned = (raw_text or "").strip()
    # Defensive: strip ```json fences if model added them despite instructions.
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = _json.loads(cleaned)
    except (ValueError, TypeError):
        return JsonResponse(
            {"error": "Generation produced invalid output, please retry."},
            status=502,
        )

    warnings = []
    hints_out = []
    use_cases_out = []
    accent_out = ""

    raw_hints = data.get("hints") if isinstance(data, dict) else None
    if (
        isinstance(raw_hints, list)
        and len(raw_hints) == 4
        and all(isinstance(h, str) and h.strip() for h in raw_hints)
    ):
        hints_out = [h.strip() for h in raw_hints]
    else:
        warnings.append("hints")

    raw_use_cases = data.get("use_cases") if isinstance(data, dict) else None
    if (
        isinstance(raw_use_cases, list)
        and len(raw_use_cases) == 4
        and all(isinstance(u, str) and u.strip() for u in raw_use_cases)
    ):
        use_cases_out = [u.strip() for u in raw_use_cases]
    else:
        warnings.append("use_cases")

    raw_accent = data.get("accent_bg", "") if isinstance(data, dict) else ""
    if isinstance(raw_accent, str) and _is_valid_hex_color(raw_accent.strip()):
        accent_out = raw_accent.strip()
    else:
        warnings.append("accent_bg")

    # If every field failed validation the model output is fundamentally broken;
    # return 502 so admin retries instead of starting from a blank slate.
    if len(warnings) == 3:
        return JsonResponse(
            {"error": "Generation produced unusable output, please retry."},
            status=502,
        )

    return JsonResponse({
        "hints": hints_out,
        "use_cases": use_cases_out,
        "accent_bg": accent_out,
        "warnings": warnings,
    })


@csrf_exempt
@login_required_api
def api_admin_agent_prompts(request, agent_id):
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)
    agent = Agent.objects.filter(id=agent_id).first()
    if not agent:
        return JsonResponse({"error": "Agent not found"}, status=404)
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    prompt_type = str(payload.get("prompt_type", "hint")).strip().lower()
    content = str(payload.get("content", "")).strip()
    sort_order = _to_non_negative_int(payload.get("sort_order", 100), default=100)
    if prompt_type not in {"hint", "use_case"}:
        return JsonResponse({"error": "prompt_type must be hint or use_case"}, status=400)
    if not content:
        return JsonResponse({"error": "content is required"}, status=400)
    prompt = AgentPrompt.objects.create(
        agent=agent,
        prompt_type=prompt_type,
        content=content,
        sort_order=sort_order,
    )
    return JsonResponse(
        {
            "id": prompt.id,
            "agent_id": agent.id,
            "prompt_type": prompt.prompt_type,
            "content": prompt.content,
            "sort_order": prompt.sort_order,
        },
        status=201,
    )


@csrf_exempt
@login_required_api
def api_admin_agent_prompt_detail(request, prompt_id):
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)
    prompt = AgentPrompt.objects.filter(id=prompt_id).first()
    if not prompt:
        return JsonResponse({"error": "Prompt not found"}, status=404)
    if request.method == "DELETE":
        prompt.delete()
        return JsonResponse({"deleted": True})
    return JsonResponse({"error": "Method not allowed"}, status=405)


def _normalize_header(header):
    cleaned = re.sub(r"[^a-z0-9]+", "", str(header or "").strip().lower())
    return HEADER_ALIASES.get(cleaned, cleaned)


def _normalize_industry(raw_industry):
    key = str(raw_industry or "").strip().lower()
    return INDUSTRY_MAP.get(key, key)


def _extract_rows_from_upload(uploaded_file):
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    rows = []
    if ext == ".csv":
        content = uploaded_file.read().decode("utf-8-sig", errors="ignore")
        reader = csv.DictReader(io.StringIO(content))
        for raw_row in reader:
            normalized = {_normalize_header(k): (v or "").strip() for k, v in raw_row.items()}
            rows.append(normalized)
        return rows
    if ext in {".xlsx", ".xlsm"}:
        if load_workbook is None:
            raise ValueError("openpyxl is required for .xlsx uploads")
        workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
        sheet = workbook.active
        row_iter = sheet.iter_rows(values_only=True)
        headers = next(row_iter, None)
        if not headers:
            return []
        normalized_headers = [_normalize_header(h) for h in headers]
        for raw_values in row_iter:
            if not raw_values or all(v is None or str(v).strip() == "" for v in raw_values):
                continue
            row = {}
            for idx, value in enumerate(raw_values):
                key = normalized_headers[idx] if idx < len(normalized_headers) else f"col_{idx}"
                row[key] = str(value).strip() if value is not None else ""
            rows.append(row)
        return rows
    raise ValueError("Unsupported file type. Use .csv or .xlsx")


def _extract_text_from_uploaded_file(file_name, file_bytes):
    ext = os.path.splitext(file_name)[1].lower()
    text = ""
    if ext in {".txt", ".md", ".csv", ".json"}:
        text = file_bytes.decode("utf-8", errors="ignore")
    elif ext == ".pdf":
        try:
            pypdf_module = importlib.import_module("pypdf")
            PdfReader = getattr(pypdf_module, "PdfReader")
            reader = PdfReader(io.BytesIO(file_bytes))
            parts = []
            for page in reader.pages[:20]:
                extracted = page.extract_text() or ""
                if extracted.strip():
                    parts.append(extracted)
            text = "\n".join(parts)
        except Exception:
            text = ""
    return text.strip()


def _upload_to_cloudinary(file_name, file_bytes):
    if not (
        cloudinary
        and settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    ):
        return None
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    uploaded = cloudinary.uploader.upload(
        io.BytesIO(file_bytes),
        resource_type="raw",
        folder="aikonik/chat_uploads",
        public_id=f"{uuid.uuid4()}-{os.path.splitext(file_name)[0][:40]}",
        use_filename=False,
        overwrite=True,
    )
    return uploaded.get("secure_url")


@csrf_exempt
@login_required_api
def api_admin_import_prompts(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    try:
        rows = _extract_rows_from_upload(uploaded_file)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    required_keys = {"industry", "category", "prompt_title", "prompt_full_text"}
    created = 0
    updated = 0
    skipped = 0
    errors = []

    for index, row in enumerate(rows, start=2):
        if not required_keys.issubset(set(row.keys())):
            missing = sorted(list(required_keys.difference(set(row.keys()))))
            return JsonResponse(
                {"error": f"Missing required columns: {', '.join(missing)}"}, status=400
            )

        title = row.get("prompt_title", "").strip()
        body = row.get("prompt_full_text", "").strip()
        industry = _normalize_industry(row.get("industry", ""))
        category = row.get("category", "").strip()
        sub_category = row.get("sub_category", "").strip()
        tags = row.get("tags", "").strip()
        difficulty = row.get("difficulty", "").strip()
        use_case_type = row.get("use_case_type", "").strip()
        estimated_time_saved = row.get("estimated_time_saved", "").strip()

        if not title or not body or not industry:
            skipped += 1
            errors.append({"row": index, "error": "Missing title/body/industry"})
            continue

        normalized_category = category or "General"
        if sub_category:
            normalized_category = f"{normalized_category} / {sub_category}"
        metadata_parts = [
            f"Difficulty: {difficulty}" if difficulty else "",
            f"Use Case Type: {use_case_type}" if use_case_type else "",
            f"Estimated Time Saved: {estimated_time_saved}" if estimated_time_saved else "",
            f"Tags: {tags}" if tags else "",
        ]
        metadata = " | ".join([part for part in metadata_parts if part])
        full_body = body if not metadata else f"{body}\n\n[{metadata}]"

        prompt, was_created = Prompt.objects.get_or_create(
            title=title,
            industry=industry,
            defaults={
                "body": full_body,
                "category": normalized_category,
                "status": "approved",
                "created_by": request.current_user,
            },
        )
        if was_created:
            created += 1
            continue

        changed = False
        if prompt.body != full_body:
            prompt.body = full_body
            changed = True
        if prompt.category != normalized_category:
            prompt.category = normalized_category
            changed = True
        if changed:
            prompt.save(update_fields=["body", "category"])
            updated += 1
        else:
            skipped += 1

    return JsonResponse(
        {
            "total_rows": len(rows),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors[:50],
        }
    )


@login_required_api
def api_dashboard(request):
    user = request.current_user
    sessions_count = ChatSession.objects.filter(user=user).count()
    saved_count = SavedPrompt.objects.filter(user=user).count()
    chats_this_week = ChatMessage.objects.filter(session__user=user, role="user").count()
    return JsonResponse(
        {
            "user_name": f"{user.first_name} {user.last_name}".strip(),
            "industry": user.industry,
            "metrics": {
                "agent_sessions": sessions_count,
                "saved_prompts": saved_count,
                "courses_enrolled": 0,
                "sessions_this_week": chats_this_week,
            },
        }
    )


# Blended token cost estimate: $0.50/1M tokens (gpt-4.1-mini rough average of input $0.40 + output $1.60).
# TODO: split ChatMessage.token_count into input/output columns for accurate cost attribution.
_BLENDED_COST_PER_TOKEN = 0.50 / 1_000_000


@csrf_exempt
@login_required_api
def api_pulse(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    now = dj_tz.now()
    today = now.date()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    signups_today = CustomUser.objects.filter(created_at__date=today).count()
    signups_week = CustomUser.objects.filter(created_at__gte=week_ago).count()

    active_today = CustomUser.objects.filter(last_active_at__gte=day_ago).count()
    active_week = CustomUser.objects.filter(last_active_at__gte=week_ago).count()

    messages_today = ChatMessage.objects.filter(role="user", created_at__date=today).count()
    messages_week = ChatMessage.objects.filter(role="user", created_at__gte=week_ago).count()

    tokens_today = (
        ChatMessage.objects.filter(role="assistant", created_at__date=today)
        .aggregate(total=Sum("token_count"))["total"] or 0
    )
    tokens_month = (
        ChatMessage.objects.filter(role="assistant", created_at__gte=month_start)
        .aggregate(total=Sum("token_count"))["total"] or 0
    )
    cost_today = round(tokens_today * _BLENDED_COST_PER_TOKEN, 4)
    cost_month = round(tokens_month * _BLENDED_COST_PER_TOKEN, 4)

    errors_today = ErrorLog.objects.filter(created_at__gte=day_ago).count()
    error_by_type = {
        row["error_type"]: row["n"]
        for row in ErrorLog.objects.filter(created_at__gte=day_ago)
        .values("error_type")
        .annotate(n=Count("id"))
    }

    total_users = CustomUser.objects.count()
    completed_users = CustomUser.objects.exclude(display_name="").count()
    profile_rate = round(completed_users / total_users * 100) if total_users else 0

    return JsonResponse({
        "signups": {"today": signups_today, "week": signups_week},
        "active_users": {"today": active_today, "week": active_week},
        "messages": {"today": messages_today, "week": messages_week},
        "tokens": {
            "today": tokens_today,
            "month": tokens_month,
            "estimated_cost_usd_today": cost_today,
            "estimated_cost_usd_month": cost_month,
        },
        "errors": {"today": errors_today, "by_type": error_by_type},
        "profile_completion": {
            "rate": profile_rate,
            "completed": completed_users,
            "total": total_users,
        },
    })


def _parse_active_after(value):
    """Parse active_after param: relative '24h'/'7d' or ISO datetime string."""
    now = dj_tz.now()
    if value.endswith("h"):
        try:
            return now - timedelta(hours=int(value[:-1]))
        except ValueError:
            return None
    if value.endswith("d"):
        try:
            return now - timedelta(days=int(value[:-1]))
        except ValueError:
            return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            from django.utils.timezone import make_aware
            dt = make_aware(dt)
        return dt
    except ValueError:
        return None


def _build_user_queryset(params):
    qs = CustomUser.objects.annotate(
        message_count=Count(
            "chat_sessions__messages",
            filter=Q(chat_sessions__messages__role="user"),
            distinct=True,
        ),
        session_count=Count("chat_sessions", distinct=True),
    )

    search = params.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(display_name__icontains=search)
            | Q(role__icontains=search)
        )

    industry = params.get("industry", "").strip().lower()
    if industry:
        qs = qs.filter(industry__iexact=INDUSTRY_MAP.get(industry, industry))

    has_profile = params.get("has_profile", "").strip().lower()
    if has_profile == "true":
        qs = qs.exclude(display_name="")
    elif has_profile == "false":
        qs = qs.filter(display_name="")

    signup_after = params.get("signup_after", "").strip()
    if signup_after:
        try:
            qs = qs.filter(created_at__date__gte=datetime.fromisoformat(signup_after).date())
        except ValueError:
            pass

    signup_before = params.get("signup_before", "").strip()
    if signup_before:
        try:
            qs = qs.filter(created_at__date__lte=datetime.fromisoformat(signup_before).date())
        except ValueError:
            pass

    active_after = params.get("active_after", "").strip()
    if active_after:
        cutoff = _parse_active_after(active_after)
        if cutoff:
            qs = qs.filter(last_active_at__gte=cutoff)

    is_suspended = params.get("is_suspended", "").strip().lower()
    if is_suspended == "true":
        qs = qs.filter(is_suspended=True)
    elif is_suspended == "false":
        qs = qs.filter(is_suspended=False)

    is_admin_filter = params.get("is_admin", "").strip().lower()
    if is_admin_filter in ("true", "false"):
        # Django auth bridge lookup — one extra query; intentionally more expensive than other filters.
        DjangoUser = get_user_model()
        su_qs = DjangoUser.objects.filter(is_superuser=True)
        admin_ids = {v.strip().lower() for v in su_qs.values_list("email", flat=True)}
        admin_ids |= {v.strip().lower() for v in su_qs.values_list("username", flat=True)}
        if is_admin_filter == "true":
            qs = qs.filter(email__in=admin_ids)
        else:
            qs = qs.exclude(email__in=admin_ids)

    sort_map = {
        "signup_desc":   ["-created_at"],
        "signup_asc":    ["created_at"],
        "active_desc":   ["-last_active_at"],
        "active_asc":    ["last_active_at"],
        "messages_desc": ["-message_count"],
        "name_asc":      ["first_name", "last_name"],
    }
    qs = qs.order_by(*sort_map.get(params.get("sort", "signup_desc").strip(), ["-created_at"]))
    return qs


def _serialize_user_item(user, superuser_emails, superuser_usernames):
    email = (user.email or "").strip().lower()
    is_admin = email in superuser_emails or email in superuser_usernames
    if not is_admin and email.endswith("@local.user"):
        is_admin = email.split("@", 1)[0] in superuser_usernames

    def iso(dt):
        return dt.isoformat().replace("+00:00", "Z") if dt else None

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": user.display_name,
        "role": user.role,
        "industry": user.industry,
        "date_joined": iso(user.created_at),
        "last_active_at": iso(user.last_active_at),
        "is_suspended": user.is_suspended,
        "is_admin": is_admin,
        "message_count": getattr(user, "message_count", 0) or 0,
        "session_count": getattr(user, "session_count", 0) or 0,
        "has_profile": bool(user.display_name),
    }


def _serialize_user_full(target, superuser_emails, superuser_usernames):
    """All-fields user serialization for admin detail/edit responses.

    Unlike _serialize_user_item (which carries annotated counts from the list
    queryset), this version includes all 18 profile fields. message_count and
    session_count are computed separately by the detail endpoint and surfaced
    under the 'stats' key, not here.
    """
    email = (target.email or "").strip().lower()
    is_admin = email in superuser_emails or email in superuser_usernames
    if not is_admin and email.endswith("@local.user"):
        is_admin = email.split("@", 1)[0] in superuser_usernames

    def iso(dt):
        return dt.isoformat().replace("+00:00", "Z") if dt else None

    return {
        "id": target.id,
        "email": target.email,
        "first_name": target.first_name,
        "last_name": target.last_name,
        "is_suspended": target.is_suspended,
        "is_admin": is_admin,
        "date_joined": iso(target.created_at),
        "last_active_at": iso(target.last_active_at),
        "industry": target.industry,
        "display_name": target.display_name,
        "role": target.role,
        "company_size": target.company_size,
        "years_experience": target.years_experience,
        "timezone": target.timezone,
        "communication_style": target.communication_style,
        "response_length": target.response_length,
        "expertise_level": target.expertise_level,
        "formality": target.formality,
        "emoji_use": target.emoji_use,
        "pushback_style": target.pushback_style,
        "explanation_style": target.explanation_style,
        "clarifying_questions": target.clarifying_questions,
        "expertise_areas": target.expertise_areas,
        "current_focus": target.current_focus,
        "things_to_avoid": target.things_to_avoid,
        "about_me": target.about_me,
    }


@csrf_exempt
@login_required_api
def api_admin_users(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    qs = _build_user_queryset(request.GET)

    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(200, max(1, int(request.GET.get("page_size", 50))))
    except (ValueError, TypeError):
        page_size = 50

    total = qs.count()
    pages = max(1, (total + page_size - 1) // page_size)
    users_page = list(qs[(page - 1) * page_size:(page - 1) * page_size + page_size])

    DjangoUser = get_user_model()
    superusers = list(DjangoUser.objects.filter(is_superuser=True).values("email", "username"))
    superuser_emails = {su["email"].strip().lower() for su in superusers}
    superuser_usernames = {su["username"].strip().lower() for su in superusers}

    return JsonResponse({
        "items": [_serialize_user_item(u, superuser_emails, superuser_usernames) for u in users_page],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    })


@csrf_exempt
@login_required_api
def api_admin_users_export(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    qs = _build_user_queryset(request.GET)
    total = qs.count()

    if total > 10_000:
        return JsonResponse(
            {
                "error": (
                    f"Export exceeds the 10,000-user limit ({total:,} matched). "
                    "Apply tighter filters to narrow down. "
                    "Streaming exports for larger sets are a planned future enhancement."
                )
            },
            status=413,
        )

    DjangoUser = get_user_model()
    superusers = list(DjangoUser.objects.filter(is_superuser=True).values("email", "username"))
    superuser_emails = {su["email"].strip().lower() for su in superusers}
    superuser_usernames = {su["username"].strip().lower() for su in superusers}

    today_str = dj_tz.now().strftime("%Y-%m-%d")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="users-{today_str}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id", "email", "first_name", "last_name", "display_name", "role",
        "industry", "company_size", "years_experience", "date_joined",
        "last_active_at", "is_suspended", "is_admin", "message_count",
        "session_count", "has_profile", "expertise_areas",
    ])
    for user in qs.iterator():
        item = _serialize_user_item(user, superuser_emails, superuser_usernames)
        expertise = ", ".join(user.expertise_areas) if isinstance(user.expertise_areas, list) else ""
        writer.writerow([
            item["id"], item["email"], item["first_name"], item["last_name"],
            item["display_name"], item["role"], item["industry"],
            user.company_size, user.years_experience,
            item["date_joined"], item["last_active_at"],
            item["is_suspended"], item["is_admin"],
            item["message_count"], item["session_count"],
            item["has_profile"], expertise,
        ])

    active_filters = {k: v for k, v in request.GET.items() if v and k not in ("page", "page_size")}
    record_admin_action(
        admin=request.current_user,
        action_type="user.export",
        target_type="user",
        metadata={"count": total, "filters": active_filters},
    )
    return response


# ── User detail (GET + PATCH) ───────────────────────────────────────────────

@csrf_exempt
@login_required_api
def api_admin_user_detail(request, user_id):
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    target = CustomUser.objects.filter(id=user_id).first()
    if not target:
        return JsonResponse({"error": "User not found"}, status=404)

    if request.method == "GET":
        DjangoUser = get_user_model()
        superusers = list(DjangoUser.objects.filter(is_superuser=True).values("email", "username"))
        superuser_emails = {su["email"].strip().lower() for su in superusers}
        superuser_usernames = {su["username"].strip().lower() for su in superusers}

        now = dj_tz.now()
        thirty_ago = now - timedelta(days=30)
        seven_ago = now - timedelta(days=7)

        message_count = ChatMessage.objects.filter(session__user=target, role="user").count()
        session_count = ChatSession.objects.filter(user=target).count()

        top_agents = list(
            ChatSession.objects.filter(user=target)
            .values("agent_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )

        top_prompts_qs = (
            SavedPrompt.objects.filter(user=target)
            .select_related("prompt")
            .annotate(total_saves=Count("prompt__saved_by", distinct=True))
            .order_by("-created_at")[:5]
        )

        first_msg = (
            ChatMessage.objects.filter(session__user=target, role="user")
            .order_by("created_at")
            .values("created_at")
            .first()
        )

        # Distinct active days: fetch datetimes, extract unique UTC dates in Python.
        # Per-user message volume is small enough that this is efficient.
        active_dates_raw = list(
            ChatMessage.objects.filter(
                session__user=target, role="user", created_at__gte=thirty_ago
            ).values_list("created_at", flat=True)
        )
        active_days_30 = len({dt.date() for dt in active_dates_raw})

        messages_7d = ChatMessage.objects.filter(
            session__user=target, role="user", created_at__gte=seven_ago
        ).count()
        messages_30d = ChatMessage.objects.filter(
            session__user=target, role="user", created_at__gte=thirty_ago
        ).count()

        recent_sessions = list(
            ChatSession.objects.filter(user=target)
            .annotate(msg_count=Count("messages"))
            .order_by("-updated_at")[:20]
        )

        def iso(dt):
            return dt.isoformat().replace("+00:00", "Z") if dt else None

        return JsonResponse({
            "user": _serialize_user_full(target, superuser_emails, superuser_usernames),
            "stats": {
                "message_count": message_count,
                "session_count": session_count,
                "top_agents": [
                    {"name": a["agent_name"], "count": a["count"]} for a in top_agents
                ],
                "top_prompts": [
                    {"title": sp.prompt.title, "saved_count": sp.total_saves}
                    for sp in top_prompts_qs
                ],
                "engagement": {
                    "first_active": iso(first_msg["created_at"]) if first_msg else None,
                    "last_active_at": iso(target.last_active_at),
                    "active_days_last_30": active_days_30,
                    "messages_last_7d": messages_7d,
                    "messages_last_30d": messages_30d,
                },
            },
            "sessions": [
                {
                    "id": s.id,
                    "title": s.title,
                    "agent_name": s.agent_name,
                    "industry": s.industry,
                    "message_count": s.msg_count,
                    "created_at": iso(s.created_at),
                    "updated_at": iso(s.updated_at),
                }
                for s in recent_sessions
            ],
        })

    if request.method == "PATCH":
        payload = get_request_json(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)

        updates, errors = _validate_and_build_profile_updates(payload)

        if "is_suspended" in payload:
            val = payload["is_suspended"]
            if not isinstance(val, bool):
                errors["is_suspended"] = "Must be a boolean."
            elif val and target.id == request.current_user.id:
                errors["is_suspended"] = "Cannot suspend yourself."
            elif val and _is_admin_user(target):
                errors["is_suspended"] = "Cannot suspend another admin."
            else:
                updates["is_suspended"] = val

        if errors:
            return JsonResponse({"errors": errors}, status=400)

        if not updates:
            return JsonResponse({"success": True, "changed_fields": []})

        changed_fields = list(updates.keys())
        for field, value in updates.items():
            setattr(target, field, value)
        target.save(update_fields=changed_fields + ["updated_at"])

        record_admin_action(
            admin=request.current_user,
            action_type="user.edit_profile",
            target_type="user",
            target_id=target.id,
            metadata={"changed_fields": changed_fields},
        )

        DjangoUser = get_user_model()
        superusers = list(DjangoUser.objects.filter(is_superuser=True).values("email", "username"))
        superuser_emails = {su["email"].strip().lower() for su in superusers}
        superuser_usernames = {su["username"].strip().lower() for su in superusers}
        return JsonResponse({
            "success": True,
            "changed_fields": changed_fields,
            "user": _serialize_user_full(target, superuser_emails, superuser_usernames),
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


# ── Suspend / Unsuspend ─────────────────────────────────────────────────────

@csrf_exempt
@login_required_api
def api_admin_user_suspend(request, user_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    target = CustomUser.objects.filter(id=user_id).first()
    if not target:
        return JsonResponse({"error": "User not found"}, status=404)
    if target.id == request.current_user.id:
        return JsonResponse({"error": "Cannot suspend yourself."}, status=400)
    if _is_admin_user(target):
        return JsonResponse({"error": "Cannot suspend another admin."}, status=400)
    if target.is_suspended:
        return JsonResponse({"error": "User is already suspended."}, status=400)

    target.is_suspended = True
    target.save(update_fields=["is_suspended", "updated_at"])

    record_admin_action(
        admin=request.current_user,
        action_type="user.suspend",
        target_type="user",
        target_id=target.id,
        metadata={},
    )
    return JsonResponse({"ok": True})


@csrf_exempt
@login_required_api
def api_admin_user_unsuspend(request, user_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    target = CustomUser.objects.filter(id=user_id).first()
    if not target:
        return JsonResponse({"error": "User not found"}, status=404)
    if not target.is_suspended:
        return JsonResponse({"error": "User is not suspended."}, status=400)

    target.is_suspended = False
    target.save(update_fields=["is_suspended", "updated_at"])

    record_admin_action(
        admin=request.current_user,
        action_type="user.unsuspend",
        target_type="user",
        target_id=target.id,
        metadata={},
    )
    return JsonResponse({"ok": True})


# ── Impersonation ───────────────────────────────────────────────────────────

@csrf_exempt
@login_required_api
def api_admin_user_impersonate(request, user_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)

    if "_impersonated_by" in request.session:
        return JsonResponse(
            {"error": "Already in an impersonation session. Stop the current one first."},
            status=400,
        )

    target = CustomUser.objects.filter(id=user_id).first()
    if not target:
        return JsonResponse({"error": "User not found"}, status=404)
    if target.id == request.current_user.id:
        return JsonResponse({"error": "Cannot impersonate yourself."}, status=400)
    if _is_admin_user(target):
        return JsonResponse({"error": "Cannot impersonate other admins."}, status=400)
    if target.is_suspended:
        return JsonResponse({"error": "Cannot impersonate a suspended user."}, status=400)

    request.session["_impersonated_by"] = request.current_user.id
    request.session["_impersonation_started_at"] = (
        dj_tz.now().isoformat().replace("+00:00", "Z")
    )
    login_user(request, target)  # sets custom_user_id = target.id

    record_admin_action(
        admin=request.current_user,
        action_type="user.impersonate",
        target_type="user",
        target_id=target.id,
        metadata={"target_user_id": target.id, "target_email": target.email},
    )
    return JsonResponse({"ok": True, "redirect": "/dashboard/"})


@csrf_exempt
@login_required_api
def api_admin_stop_impersonation(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    if "_impersonated_by" not in request.session:
        return JsonResponse({"error": "Not currently impersonating."}, status=400)

    impersonated_user_id = request.session.get("custom_user_id")  # capture before restore
    admin_id = request.session.get("_impersonated_by")
    _do_restore_impersonation(request)  # session now points back to admin

    admin_user = CustomUser.objects.filter(id=admin_id).first()
    if admin_user:
        record_admin_action(
            admin=admin_user,
            action_type="user.stop_impersonation",
            target_type="user",
            target_id=impersonated_user_id,
            metadata={"target_user_id": impersonated_user_id},
        )
    return JsonResponse({"ok": True, "redirect": "/admin-dashboard/"})


@login_required_api
def api_prompts(request):
    ensure_seed_prompts()
    base_queryset = Prompt.objects.filter(status="approved")
    mine_only = request.GET.get("mine", "").strip() == "1"
    saved_only = request.GET.get("saved", "").strip() == "1"
    q = request.GET.get("q", "").strip()
    industry = request.GET.get("industry", "").strip().lower()
    category = request.GET.get("category", "").strip()
    queryset = Prompt.objects.filter(created_by=request.current_user) if mine_only else base_queryset
    if q:
        queryset = queryset.filter(Q(title__icontains=q) | Q(body__icontains=q))
    if industry and industry != "all":
        queryset = queryset.filter(industry__iexact=industry)
    if category and category != "All Categories":
        queryset = queryset.filter(category__iexact=category)

    user_saved_ids = set(
        SavedPrompt.objects.filter(user=request.current_user).values_list("prompt_id", flat=True)
    )
    if saved_only:
        queryset = queryset.filter(id__in=user_saved_ids)
    payload = [
        {
            "id": prompt.id,
            "title": prompt.title,
            "body": prompt.body,
            "industry": prompt.industry,
            "category": prompt.category,
            "uses": prompt.usage_count,
            "saved": prompt.id in user_saved_ids,
            "status": prompt.status,
        }
        for prompt in queryset.order_by("-usage_count", "-created_at")
    ]
    stats = {
        "total_prompts": base_queryset.count(),
        "total_industries": base_queryset.values("industry").distinct().count(),
        "total_categories": base_queryset.values("category").distinct().count(),
    }
    library = {
        "saved_count": len(user_saved_ids),
        "submissions_count": Prompt.objects.filter(created_by=request.current_user).count(),
    }
    return JsonResponse({"items": payload, "stats": stats, "library": library})


@csrf_exempt
@login_required_api
def api_submit_prompt(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    title = str(payload.get("title", "")).strip()
    body = str(payload.get("body", "")).strip()
    industry = str(payload.get("industry", "")).strip().lower()
    category = str(payload.get("category", "")).strip()
    if not title or not body or not industry:
        return JsonResponse({"error": "title, body, industry are required"}, status=400)

    prompt = Prompt.objects.create(
        title=title,
        body=body,
        industry=industry,
        category=category or "General",
        status="pending",
        created_by=request.current_user,
    )
    return JsonResponse({"id": prompt.id, "status": prompt.status}, status=201)


@csrf_exempt
@login_required_api
def api_toggle_save_prompt(request, prompt_id):
    prompt = Prompt.objects.filter(id=prompt_id).first()
    if not prompt:
        return JsonResponse({"error": "Prompt not found"}, status=404)
    if request.method == "POST":
        SavedPrompt.objects.get_or_create(user=request.current_user, prompt=prompt)
        return JsonResponse({"saved": True})
    if request.method == "DELETE":
        SavedPrompt.objects.filter(user=request.current_user, prompt=prompt).delete()
        return JsonResponse({"saved": False})
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required_api
def api_chat_sessions(request):
    sessions = ChatSession.objects.filter(user=request.current_user).order_by("-updated_at")
    return JsonResponse(
        {
            "items": [
                {
                    "id": session.id,
                    "title": session.title,
                    "agent_name": session.agent_name,
                    "industry": session.industry,
                    "updated_at": session.updated_at.isoformat(),
                }
                for session in sessions
            ]
        }
    )


@csrf_exempt
@login_required_api
def api_create_chat_session(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    payload = get_request_json(request)
    if payload is None:
        payload = {}
    session = ChatSession.objects.create(
        user=request.current_user,
        title=payload.get("title") or "New chat",
        agent_name=payload.get("agent_name") or "Contract Review Agent",
        industry=payload.get("industry") or request.current_user.industry or "legal",
    )
    return JsonResponse({"id": session.id, "title": session.title}, status=201)


@login_required_api
def api_chat_messages(request, session_id):
    session = ChatSession.objects.filter(id=session_id, user=request.current_user).first()
    if not session:
        return JsonResponse({"error": "Session not found"}, status=404)
    items = [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "token_count": message.token_count,
            "created_at": message.created_at.isoformat(),
        }
        for message in session.messages.order_by("created_at")
    ]
    return JsonResponse({"session_id": session.id, "items": items})


@csrf_exempt
@login_required_api
def api_chat_upload_file(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    file_name = uploaded_file.name or "uploaded_file"
    file_bytes = uploaded_file.read()
    if not file_bytes:
        return JsonResponse({"error": "Uploaded file is empty"}, status=400)

    extracted_text = _extract_text_from_uploaded_file(file_name, file_bytes)
    cloud_url = _upload_to_cloudinary(file_name, file_bytes)
    summary_lines = [
        f"File: {file_name}",
        f"Cloud URL: {cloud_url or 'Not available'}",
    ]
    if extracted_text:
        summary_lines.append("")
        summary_lines.append("Extracted content:")
        summary_lines.append(extracted_text[:12000])
    else:
        summary_lines.append("")
        summary_lines.append(
            "No text could be extracted automatically. Please provide instructions for this file."
        )
    return JsonResponse(
        {
            "file_name": file_name,
            "cloud_url": cloud_url,
            "extracted_text": extracted_text,
            "message_text": "\n".join(summary_lines),
        }
    )


@csrf_exempt
@login_required_api
def api_send_chat_message(request, session_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    session = ChatSession.objects.filter(id=session_id, user=request.current_user).first()
    if not session:
        return JsonResponse({"error": "Session not found"}, status=404)
    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    content = str(payload.get("content", "")).strip()
    if not content:
        return JsonResponse({"error": "content is required"}, status=400)

    request.current_user.last_active_at = dj_tz.now()
    request.current_user.save(update_fields=["last_active_at"])

    user_message = ChatMessage.objects.create(session=session, role="user", content=content)
    history = list(session.messages.order_by("created_at").values("role", "content"))
    agent = Agent.objects.filter(name=session.agent_name).first()
    agent_prompts = list(agent.prompts.all()) if agent else []
    system_content = build_full_system_prompt(agent, agent_prompts, request.current_user)
    trimmed = trim_history_to_budget(history, system_content)

    if estimate_messages_tokens(system_content, trimmed) > MAX_REQUEST_TOKENS:
        user_message.delete()
        return JsonResponse(
            {
                "error": "This message is too long. Try splitting it into smaller messages.",
                "retry_content": content,
            },
            status=413,
        )

    openai_messages = [{"role": "system", "content": system_content}]
    openai_messages.extend({"role": m["role"], "content": m["content"]} for m in trimmed)

    try:
        assistant_text, total_tokens = get_openai_reply(openai_messages)
    except Exception as exc:
        user_message.delete()
        logger.exception("Chat send failed (session=%s): %s", session.id, exc)
        log_error(
            error_type="openai_chat_send",
            message=str(exc),
            user=request.current_user,
            metadata={"session_id": session.id},
        )
        return JsonResponse(
            {
                "error": "Could not generate a reply. Please try again.",
                "retry_content": content,
            },
            status=502,
        )

    assistant = ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=assistant_text,
        token_count=total_tokens,
    )
    session.title = session.title if session.title != "New chat" else content[:60]
    session.save(update_fields=["title", "updated_at"])

    return JsonResponse(
        {
            "id": assistant.id,
            "role": "assistant",
            "content": assistant.content,
            "token_count": assistant.token_count,
        }
    )


@csrf_exempt
@login_required_api
def api_message_feedback(request, message_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    message = ChatMessage.objects.filter(id=message_id, session__user=request.current_user).first()
    if not message:
        return JsonResponse({"error": "Message not found"}, status=404)
    payload = get_request_json(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    feedback = str(payload.get("feedback", "")).strip().lower()
    if feedback not in {"up", "down"}:
        return JsonResponse({"error": "feedback must be 'up' or 'down'"}, status=400)
    message.feedback = feedback
    message.save(update_fields=["feedback"])
    return JsonResponse({"success": True, "feedback": feedback})
