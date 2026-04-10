import json
from functools import wraps

from django.http import JsonResponse

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


def login_required_api(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = get_current_user(request)
        if not user:
            return JsonResponse({"error": "Authentication required"}, status=401)
        request.current_user = user
        return view_func(request, *args, **kwargs)

    return wrapper
