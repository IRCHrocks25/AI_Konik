import json
from datetime import datetime
from functools import wraps

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone as _dj_tz

from .models import CustomUser

SESSION_USER_ID_KEY = "custom_user_id"
IMPERSONATION_TIMEOUT_SECONDS = 30 * 60  # 30 minutes


def _do_restore_impersonation(request):
    """Restore the admin's session from an active impersonation.

    Sets custom_user_id back to the stored admin id and removes both
    impersonation keys. Safe to call even if keys are absent (idempotent).
    Also called by the stop-impersonation endpoint in views.py.
    """
    admin_id = request.session.get("_impersonated_by")
    if admin_id:
        request.session[SESSION_USER_ID_KEY] = admin_id
    request.session.pop("_impersonated_by", None)
    request.session.pop("_impersonation_started_at", None)


def check_impersonation_timeout(request):
    """Auto-expire an impersonation session that has exceeded the timeout.

    Called at the top of login_required_api and admin_required *before* any
    auth read. If the timeout has passed the admin's session is silently
    restored and an audit event is recorded. The view then proceeds normally
    as the admin user — no redirect is issued here.
    """
    started_str = request.session.get("_impersonation_started_at")
    if not started_str:
        return  # not impersonating — fast path, zero DB hits

    try:
        started_at = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        # Malformed timestamp — clean up defensively and bail out
        _do_restore_impersonation(request)
        return

    elapsed = (_dj_tz.now() - started_at).total_seconds()
    if elapsed <= IMPERSONATION_TIMEOUT_SECONDS:
        return  # still within the 30-minute window

    impersonated_id = request.session.get(SESSION_USER_ID_KEY)
    admin_id = request.session.get("_impersonated_by")
    _do_restore_impersonation(request)

    # Lazy import — avoids a module-level dependency on admin_audit from auth_utils
    try:
        from .admin_audit import record_admin_action
        admin_user = CustomUser.objects.filter(id=admin_id).first()
        if admin_user:
            record_admin_action(
                admin=admin_user,
                action_type="user.impersonation_auto_expired",
                target_type="user",
                target_id=impersonated_id,
                metadata={
                    "target_user_id": impersonated_id,
                    "expired_after_seconds": int(elapsed),
                },
            )
    except Exception:
        pass  # audit failure must never block the request


def get_request_json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def login_user(request, user):
    request.session[SESSION_USER_ID_KEY] = user.id


def logout_user(request):
    request.session.pop(SESSION_USER_ID_KEY, None)


def get_current_user(request):
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        return None
    return CustomUser.objects.filter(id=user_id).first()


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


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        check_impersonation_timeout(request)
        user = get_current_user(request)
        if not user:
            return redirect("login")
        if not _is_admin_user(user):
            return redirect("dashboard")
        request.current_user = user
        return view_func(request, *args, **kwargs)
    return wrapper


def login_required_api(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        check_impersonation_timeout(request)
        user = get_current_user(request)
        if not user:
            return JsonResponse({"error": "Authentication required"}, status=401)
        if not user.email_verified:
            return JsonResponse(
                {
                    "error": "email_verification_required",
                    "message": "Please verify your email",
                },
                status=403,
            )
        request.current_user = user
        return view_func(request, *args, **kwargs)

    return wrapper
