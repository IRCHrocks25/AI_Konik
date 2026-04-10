from django.urls import path, re_path
from django.views.generic import RedirectView

from . import views

legacy_redirect = lambda target: RedirectView.as_view(  # noqa: E731
    url=target, permanent=False, query_string=True
)

urlpatterns = [
    path("", views.home, name="home"),
    path("index/", views.home, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("agents/", views.agents, name="agents"),
    path("agent-chat/", views.agent_chat, name="agent_chat"),
    path("prompts/", views.prompts, name="prompts"),
    path("industries/", views.industries, name="industries"),
    path("events/", views.events, name="events"),
    path("tools/", views.tools, name="tools"),
    path("consulting/", views.consulting, name="consulting"),
    path("billing/", views.billing, name="billing"),
    path("login/", views.login, name="login"),
    path("register/", views.register, name="register"),
    path("index.html", legacy_redirect("/index/"), name="legacy_index_html"),
    path("dashboard.html", legacy_redirect("/dashboard/"), name="legacy_dashboard_html"),
    path("agents.html", legacy_redirect("/agents/"), name="legacy_agents_html"),
    path("agent-chat.html", legacy_redirect("/agent-chat/"), name="legacy_agent_chat_html"),
    path("prompts.html", legacy_redirect("/prompts/"), name="legacy_prompts_html"),
    path("industries.html", legacy_redirect("/industries/"), name="legacy_industries_html"),
    path("events.html", legacy_redirect("/events/"), name="legacy_events_html"),
    path("tools.html", legacy_redirect("/tools/"), name="legacy_tools_html"),
    path("consulting.html", legacy_redirect("/consulting/"), name="legacy_consulting_html"),
    path("billing.html", legacy_redirect("/billing/"), name="legacy_billing_html"),
    path("login.html", legacy_redirect("/login/"), name="legacy_login_html"),
    path("register.html", legacy_redirect("/register/"), name="legacy_register_html"),
    path("prompt-import.html", legacy_redirect("/prompt-import/"), name="legacy_prompt_import_html"),
    re_path(
        r"^(?:.*/)?(?P<page>(index|dashboard|agents|agent-chat|prompts|industries|events|tools|consulting|billing|login|register|prompt-import)\.html)$",
        views.legacy_html_redirect,
        name="legacy_nested_html_redirect",
    ),
    path(
        "courses.html",
        RedirectView.as_view(url="https://courseforge.katek-ai.com/", permanent=False),
        name="courses_redirect_html",
    ),
    path(
        "courses/",
        RedirectView.as_view(url="https://courseforge.katek-ai.com/", permanent=False),
        name="courses_redirect",
    ),
    path("prompt-import/", views.prompt_import_dashboard, name="prompt_import_dashboard"),
    path("shared.css", views.shared_css, name="shared_css"),
    path("api/auth/register", views.api_register, name="api_register"),
    path("api/auth/login", views.api_login, name="api_login"),
    path("api/auth/logout", views.api_logout, name="api_logout"),
    path("api/auth/me", views.api_me, name="api_me"),
    path("api/dashboard", views.api_dashboard, name="api_dashboard"),
    path("api/prompts", views.api_prompts, name="api_prompts"),
    path("api/prompts/submit", views.api_submit_prompt, name="api_submit_prompt"),
    path("api/prompts/<int:prompt_id>/save", views.api_toggle_save_prompt, name="api_toggle_save_prompt"),
    path("api/chat/sessions", views.api_chat_sessions, name="api_chat_sessions"),
    path("api/chat/sessions/create", views.api_create_chat_session, name="api_create_chat_session"),
    path("api/chat/sessions/<int:session_id>/messages", views.api_chat_messages, name="api_chat_messages"),
    path("api/chat/upload-file", views.api_chat_upload_file, name="api_chat_upload_file"),
    path("api/chat/sessions/<int:session_id>/send", views.api_send_chat_message, name="api_send_chat_message"),
    path("api/chat/messages/<int:message_id>/feedback", views.api_message_feedback, name="api_message_feedback"),
    path("api/admin/prompts/import", views.api_admin_import_prompts, name="api_admin_import_prompts"),
]
