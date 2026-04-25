import json
from functools import wraps

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import CustomUser

SESSION_USER_ID_KEY = "custom_user_id"


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
        user = get_current_user(request)
        if not user:
            return JsonResponse({"error": "Authentication required"}, status=401)
        request.current_user = user
        return view_func(request, *args, **kwargs)

    return wrapper
