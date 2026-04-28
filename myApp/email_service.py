"""Resend transactional email integration.

Pure HTTP client (uses `requests` directly — no Resend SDK dependency, matching
the openai_service.py pattern in this codebase). Handles three lifecycle emails:

  * welcome verification  — sent at registration
  * day_3 check-in        — sent ~3 days after signup
  * day_14 strategy call  — sent ~14 days after signup

All sends are best-effort: on Resend API failure we log to ErrorLog and return
False. Callers must treat send failures as non-fatal — registration must not
crash if Resend is down.
"""
import logging
import os
from datetime import timedelta

import requests

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────

RESEND_API_URL = "https://api.resend.com/emails"
TOKEN_TTL = timedelta(hours=72)
CALENDLY_URL = "https://l.katalyst-crm.com/widget/bookings/discovery-call-ai-business-os"

# Lifecycle kinds — also stored on CustomUser.last_lifecycle_email_kind
KIND_WELCOME = "welcome"
KIND_DAY_3 = "day_3"
KIND_DAY_14 = "day_14"

# Email-safe brand color (indigo). Inline only — Gmail strips <style> blocks.
ACCENT = "#6366f1"
ACCENT_DARK = "#4f46e5"
INK = "#0f172a"
SLATE = "#475569"
BORDER = "#e5e7eb"

SIGNATURE = "The Ikonik team"

# Connect/read timeouts (seconds). Generous on read since transactional senders
# can occasionally take a few seconds; tight on connect to fail fast on outages.
_HTTP_TIMEOUT = (5, 15)


# ── Public API ──────────────────────────────────────────────────────


def send_welcome_verification_email(user, *, request=None):
    """Send the welcome + verification email to a freshly registered user.

    Uses request.build_absolute_uri when available so the link works in dev
    (localhost:8000) and prod (railway domain) without hardcoding a host.
    """
    verify_url = _build_verify_url(user, request=request)
    subject = "Verify your email to get started with Ikonik"
    html = _render_welcome_html(user, verify_url)
    text = _render_welcome_text(user, verify_url)
    return _send(
        to=user.email,
        subject=subject,
        html=html,
        text=text,
        kind=KIND_WELCOME,
        user=user,
    )


def send_day_3_email(user):
    subject = "How's your first week with Ikonik?"
    html = _render_day3_html(user)
    text = _render_day3_text(user)
    return _send(
        to=user.email,
        subject=subject,
        html=html,
        text=text,
        kind=KIND_DAY_3,
        user=user,
    )


def send_day_14_email(user, *, agents_used, prompts_run):
    subject = "You've been with Ikonik for 2 weeks — let's chat"
    html = _render_day14_html(user, agents_used=agents_used, prompts_run=prompts_run)
    text = _render_day14_text(user, agents_used=agents_used, prompts_run=prompts_run)
    return _send(
        to=user.email,
        subject=subject,
        html=html,
        text=text,
        kind=KIND_DAY_14,
        user=user,
    )


# ── Internals ───────────────────────────────────────────────────────


def _send(*, to, subject, html, text, kind, user=None):
    """POST to Resend's /emails endpoint. Returns (ok: bool, info: dict).

    Never raises. On any failure path (no API key, network error, non-2xx,
    JSON parse error) logs to ErrorLog and returns (False, {...}).
    """
    api_key = os.environ.get("RESEND_API_KEY", "")
    sender = os.environ.get("RESEND_FROM", "aikonik <noreply@katek-ai.com>")

    if not api_key:
        _log_email_error(
            user=user,
            message="RESEND_API_KEY not configured; email not sent",
            metadata={"kind": kind, "to": to},
        )
        return False, {"error": "missing_api_key"}

    payload = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            RESEND_API_URL, json=payload, headers=headers, timeout=_HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        _log_email_error(
            user=user,
            message=f"Resend network error: {exc!s}",
            metadata={"kind": kind, "to": to},
        )
        return False, {"error": "network_error"}

    if resp.status_code >= 400:
        body_snippet = (resp.text or "")[:300]
        _log_email_error(
            user=user,
            message=f"Resend API {resp.status_code}: {body_snippet}",
            metadata={"kind": kind, "to": to, "status": resp.status_code},
        )
        return False, {"error": "api_error", "status": resp.status_code}

    try:
        data = resp.json()
    except ValueError:
        data = {}

    return True, {"id": data.get("id", ""), "status": resp.status_code}


def _log_email_error(*, user, message, metadata):
    """Write a failure to ErrorLog. Imported lazily to avoid module-load cycles."""
    try:
        from .models import ErrorLog
        ErrorLog.objects.create(
            error_type="email_send",
            message=str(message)[:500],
            user=user,
            metadata=metadata or {},
        )
    except Exception:
        # Last-resort: never let logging itself crash the caller.
        logger.exception("Failed to record email_send ErrorLog entry")


def _build_verify_url(user, *, request=None):
    """Build the absolute verify-email link the user clicks from their inbox."""
    token = str(user.email_verification_token or "")
    path = f"/verify-email/?token={token}"
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            pass
    base = os.environ.get("APP_BASE_URL", "").rstrip("/")
    return f"{base}{path}" if base else path


def _greeting(user):
    name = (getattr(user, "first_name", "") or "").strip()
    return f"Hi {name}," if name else "Hello,"


# ── Templates (inline-styled, table-based, Gmail-safe) ──────────────
#
# Constraints:
#   * No <style> blocks (Gmail strips them).
#   * No flexbox / grid / CSS variables / @media.
#   * System font stack only.
#   * Single accent color via inline style.
#   * Tables for layout where centered/constrained widths matter.


def _shell(inner_html):
    """Wrap content in a max-width 560px container with system font."""
    return (
        '<!doctype html><html><body style="margin:0;padding:0;background:#f8fafc;'
        'font-family:Helvetica,Arial,sans-serif;color:' + INK + ';">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f8fafc;padding:32px 16px;">'
        '<tr><td align="center">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#ffffff;border:1px solid ' + BORDER + ';'
        'border-radius:12px;padding:32px;">'
        + inner_html
        + '</table></td></tr></table></body></html>'
    )


def _button(label, url):
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="margin:24px 0;"><tr><td align="left">'
        f'<a href="{url}" '
        f'style="display:inline-block;background:{ACCENT};color:#ffffff;'
        f'text-decoration:none;font-weight:600;font-size:15px;padding:12px 22px;'
        f'border-radius:8px;">{label}</a>'
        '</td></tr></table>'
    )


def _signoff():
    return (
        f'<p style="margin:24px 0 0 0;font-size:14px;color:{SLATE};line-height:1.6;">'
        f'— {SIGNATURE}</p>'
    )


# Welcome verification ----------------------------------------------------------------


def _render_welcome_html(user, verify_url):
    inner = (
        '<tr><td>'
        '<div style="font-size:14px;font-weight:600;color:' + ACCENT_DARK + ';'
        'margin-bottom:8px;">Ikonik</div>'
        '<h1 style="margin:0 0 12px 0;font-size:22px;color:' + INK + ';">'
        'Welcome to Ikonik</h1>'
        f'<p style="margin:0 0 12px 0;font-size:15px;line-height:1.6;color:{INK};">'
        f'{_greeting(user)} thanks for signing up. One quick step before we '
        'set up your workspace: verify your email.</p>'
        + _button("Verify my email", verify_url) +
        f'<p style="margin:0 0 8px 0;font-size:13px;color:{SLATE};line-height:1.6;">'
        'Or paste this link into your browser:</p>'
        f'<p style="margin:0 0 8px 0;font-size:12px;color:{SLATE};word-break:break-all;">'
        f'<a href="{verify_url}" style="color:{ACCENT_DARK};">{verify_url}</a></p>'
        f'<p style="margin:16px 0 0 0;font-size:12px;color:{SLATE};line-height:1.6;">'
        'This link expires in 72 hours. If you did not create an Ikonik '
        'account, you can ignore this message.</p>'
        + _signoff()
        + '</td></tr>'
    )
    return _shell(inner)


def _render_welcome_text(user, verify_url):
    return (
        f"{_greeting(user)}\n\n"
        "Welcome to Ikonik. Please verify your email to get started:\n\n"
        f"{verify_url}\n\n"
        "This link expires in 72 hours. If you did not create an Ikonik "
        "account, you can ignore this message.\n\n"
        f"— {SIGNATURE}\n"
    )


# Day 3 check-in ----------------------------------------------------------------------


def _render_day3_html(user):
    inner = (
        '<tr><td>'
        '<div style="font-size:14px;font-weight:600;color:' + ACCENT_DARK + ';'
        'margin-bottom:8px;">Ikonik</div>'
        '<h1 style="margin:0 0 12px 0;font-size:22px;color:' + INK + ';">'
        'How\'s it going?</h1>'
        f'<p style="margin:0 0 12px 0;font-size:15px;line-height:1.6;color:{INK};">'
        f'{_greeting(user)} you\'re a few days into Ikonik. Three quick tips '
        'while you settle in:</p>'
        f'<ul style="margin:0 0 16px 18px;padding:0;font-size:14px;color:{INK};line-height:1.7;">'
        '<li>Pick an agent that matches your most common task — agents bring '
        'their own context so you skip the prompt warm-up.</li>'
        '<li>Save prompts you reuse. They show up in your library on the '
        'left rail.</li>'
        '<li>Personalize your profile (Settings → Profile). It quietly tunes '
        'every reply to your style and expertise.</li>'
        '</ul>'
        f'<p style="margin:0 0 8px 0;font-size:15px;line-height:1.6;color:{INK};">'
        'Stuck on anything? Book a free 30-minute call and we\'ll help you '
        'get more out of Ikonik:</p>'
        + _button("Book a call", CALENDLY_URL)
        + _signoff()
        + '</td></tr>'
    )
    return _shell(inner)


def _render_day3_text(user):
    return (
        f"{_greeting(user)}\n\n"
        "You're a few days into Ikonik — quick tips:\n\n"
        "  - Pick an agent that matches your most common task; agents skip "
        "the prompt warm-up.\n"
        "  - Save prompts you reuse — they show up in your library.\n"
        "  - Personalize your profile (Settings → Profile) to tune every "
        "reply to your style.\n\n"
        "Stuck on anything? Book a free 30-minute call:\n"
        f"{CALENDLY_URL}\n\n"
        f"— {SIGNATURE}\n"
    )


# Day 14 strategy call ---------------------------------------------------------------


def _render_day14_html(user, *, agents_used, prompts_run):
    stats_line = (
        f'You\'ve used {agents_used} agent{"s" if agents_used != 1 else ""} '
        f'and run {prompts_run} prompt{"s" if prompts_run != 1 else ""}.'
    )
    inner = (
        '<tr><td>'
        '<div style="font-size:14px;font-weight:600;color:' + ACCENT_DARK + ';'
        'margin-bottom:8px;">Ikonik</div>'
        '<h1 style="margin:0 0 12px 0;font-size:22px;color:' + INK + ';">'
        'Two weeks in — how can we help you go further?</h1>'
        f'<p style="margin:0 0 12px 0;font-size:15px;line-height:1.6;color:{INK};">'
        f'{_greeting(user)} you\'ve been with Ikonik for two weeks. '
        f'{stats_line}</p>'
        f'<p style="margin:0 0 12px 0;font-size:15px;line-height:1.6;color:{INK};">'
        'Want to maximize Ikonik for your team? Grab a 30-minute strategy '
        'call with us — we\'ll look at your workflow and recommend the '
        'agents and integrations that\'ll move the needle.</p>'
        + _button("Book a strategy call", CALENDLY_URL)
        + _signoff()
        + '</td></tr>'
    )
    return _shell(inner)


def _render_day14_text(user, *, agents_used, prompts_run):
    stats_line = (
        f"You've used {agents_used} agent{'s' if agents_used != 1 else ''} "
        f"and run {prompts_run} prompt{'s' if prompts_run != 1 else ''}."
    )
    return (
        f"{_greeting(user)}\n\n"
        f"You've been with Ikonik for two weeks. {stats_line}\n\n"
        "Want to maximize Ikonik? Grab a free 30-minute strategy call:\n"
        f"{CALENDLY_URL}\n\n"
        f"— {SIGNATURE}\n"
    )
