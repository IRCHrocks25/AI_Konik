import csv
import importlib
import io
import os
import re
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone as dj_tz
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt

from .auth_utils import (
    get_current_user,
    get_request_json,
    login_required_api,
    login_user,
    logout_user,
)
from .models import Agent, AgentPrompt, ChatMessage, ChatSession, CustomUser, Prompt, SavedPrompt
from .openai_service import get_openai_reply
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


def _is_admin_user(custom_user):
    if not custom_user:
        return False
    django_user_model = get_user_model()
    email = (custom_user.email or "").strip().lower()
    django_user = django_user_model.objects.filter(
        Q(email__iexact=email) | Q(username__iexact=email)
    ).first()
    if not django_user and email.endswith("@local.user"):
        username_guess = email.split("@", 1)[0]
        django_user = django_user_model.objects.filter(username__iexact=username_guess).first()
    return bool(django_user and django_user.is_superuser)


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
    user = get_current_user(request)
    if not user:
        return JsonResponse({"authenticated": False, "is_admin": False})
    return JsonResponse(
        {
            "authenticated": True,
            "is_admin": _is_admin_user(user),
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "industry": user.industry,
        }
    )


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

    errors = {}
    updates = {}

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
        if not name or not industry or not description:
            return JsonResponse({"error": "name, industry, and description are required"}, status=400)
        slug = slugify(name)
        if not slug:
            return JsonResponse({"error": "Invalid name"}, status=400)
        if Agent.objects.filter(Q(name__iexact=name) | Q(slug=slug)).exists():
            return JsonResponse({"error": "Agent already exists"}, status=409)
        agent = Agent.objects.create(
            name=name,
            slug=slug,
            industry=industry,
            description=description,
            icon_class=str(payload.get("icon_class", "fa-robot")).strip() or "fa-robot",
            accent_bg=str(payload.get("accent_bg", "#EEF2FF")).strip() or "#EEF2FF",
            tag=str(payload.get("tag", "")).strip(),
            usage_count=_to_non_negative_int(payload.get("usage_count", 0), default=0),
            is_featured=bool(payload.get("is_featured", False)),
            is_active=bool(payload.get("is_active", True)),
            sort_order=_to_non_negative_int(payload.get("sort_order", 100), default=100),
        )
        return JsonResponse(_serialize_agent(agent, include_prompts=True), status=201)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@login_required_api
def api_admin_agent_detail(request, agent_id):
    if not _is_admin_user(request.current_user):
        return JsonResponse({"error": "Admin access required"}, status=403)
    agent = Agent.objects.filter(id=agent_id).first()
    if not agent:
        return JsonResponse({"error": "Agent not found"}, status=404)
    if request.method == "DELETE":
        agent.delete()
        return JsonResponse({"deleted": True})
    return JsonResponse({"error": "Method not allowed"}, status=405)


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

    ChatMessage.objects.create(session=session, role="user", content=content)
    history = list(session.messages.order_by("created_at").values("role", "content"))
    openai_messages = [
        {"role": "system", "content": "You are a practical assistant for SMB users."}
    ]
    openai_messages.extend({"role": item["role"], "content": item["content"]} for item in history)
    assistant_text, total_tokens = get_openai_reply(openai_messages)
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
