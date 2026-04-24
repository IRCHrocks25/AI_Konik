# CLAUDE.md

Project guidance for Claude Code working in this repository.

## Project At A Glance

- Run commands from the repo root (the directory containing `manage.py`).
- `myProject/` contains Django project settings and root config.
- `myApp/` contains application views, models, templates, API logic, and auth helpers.
- Templates are flat files in `myApp/templates/` (no shared base template with `extends`).

## Quick Start Commands

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
python manage.py createsuperuser
python manage.py makemigrations myApp
python manage.py test myApp
python manage.py test myApp.tests.ClassName.test_method
```

Notes:
- `createsuperuser` is required to access `/agent-admin/` and `/prompt-import/`.
- Keep migrations scoped to `myApp` unless intentionally changing other apps.

## Environment Variables

Loaded from `.env` at repo root via `python-dotenv` in `myProject/settings.py`.

Required / important:
- `OPENAI_API_KEY`: required when `DEBUG=false` (settings raises `RuntimeError` if missing).
- `DJANGO_SECRET_KEY`
- `DEBUG`

Optional:
- `DATABASE_URL`: if set, parsed via `dj_database_url` (Railway/Postgres); else `db.sqlite3`.
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`: enable remote storage for chat uploads.

Deployment host config includes `aikonik-production.up.railway.app` in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

## Core Architecture

### 1) Dual User System (Critical)

This app does **not** use Django `User` as its primary app identity.

- Primary app user: `myApp.models.CustomUser`
  - plain `models.Model`
  - stores `password_hash`
  - session auth via `myApp/auth_utils.py`
  - session key: `custom_user_id`
  - key helpers: `login_user`, `get_current_user`
  - API guard: `login_required_api`

- Django auth `User` is still used for:
  - `createsuperuser`
  - Django admin
  - superuser/admin authority checks

Bridge behavior in `api_login` (`views.py`):
- Try CustomUser login first.
- If it fails, fall back to Django auth user.
- If Django auth succeeds, create/sync corresponding `CustomUser`.

Admin gate source of truth:
- `_is_admin_user` checks matching Django auth user `is_superuser`.
- Protected areas: `/agent-admin/`, `/prompt-import/`, all `/api/admin/*`.

When editing auth, keep this bridge intact.

### 2) URL / Template Contract (Critical)

All routes live in `myApp/urls.py` (mounted at `/` from `myProject/urls.py`).

For every user-facing page, maintain **all 3** entry paths:
1. Canonical route (example: `/prompts/` -> `views.prompts` -> `prompts.html`)
2. Legacy `.html` redirect (example: `/prompts.html` -> canonical path)
3. Nested legacy redirect support via `legacy_nested_html_redirect` + `LEGACY_PATH_REDIRECTS` in `views.py`

If you add a page, update all three or legacy links/bookmarks may break.

Special case:
- `/courses/` and `/courses.html` always redirect off-site to `https://courseforge.katek-ai.com/`.

### 3) Agents / Prompts Data Model

Two related domains:
- `Prompt` / `SavedPrompt`: library shown on `/prompts/`
  - admin bulk import via `api_admin_import_prompts`
  - supports CSV/XLSX ingestion and header normalization (`HEADER_ALIASES`)
- `Agent` / `AgentPrompt`: agent catalog and attached prompts
  - managed via `/agent-admin/`
  - delivered to UI via `/api/agents`

Seeding behavior:
- Seeding is on-demand in request flow (not migration-driven).
- `ensure_seed_prompts()` and `ensure_seed_agents()` short-circuit when data already exists.
- Do not call seed functions from endpoints that should be strictly read-only/non-mutating.

Input normalization:
- Use `INDUSTRY_MAP` (`views.py`) for free-text industry normalization.

### 4) Chat Runtime Flow

Core endpoint: `POST /api/chat/sessions/<id>/send`
1. Persist user message.
2. Rebuild full session history from `ChatMessage`.
3. Prepend fixed system prompt.
4. Call `openai_service.get_openai_reply` (`gpt-4.1-mini`; `responses.create` first, fallback to `chat.completions`).
5. Persist assistant reply + token count.
6. Rename session from `"New chat"` to first user message when applicable.

Upload endpoint: `api_chat_upload_file`
- Extracts text from uploaded files (`txt`, `md`, `csv`, `json`, `pdf` via dynamic `pypdf` import).
- Optionally uploads file bytes to Cloudinary (`aikonik/chat_uploads/`) when credentials exist.
- Returns extracted `message_text` to client.
- Does **not** create `ChatMessage`; client sends extracted content in a follow-up chat send call.

## API Conventions

Most API views follow this pattern:
- `@csrf_exempt`
- `@login_required_api` (for authenticated endpoints)
- explicit method check
- parse with `auth_utils.get_request_json`
  - `{}` for empty body
  - `None` for invalid JSON
  - return `400` on `None`

Keep this behavior consistent when adding endpoints.

## Safe Change Checklist

Before finishing a change:
- If adding/editing a page route:
  - update canonical path
  - update `.html` legacy redirect
  - update `LEGACY_PATH_REDIRECTS` compatibility path
- If editing login/admin logic:
  - verify both `CustomUser` and Django `User` bridge behavior still works
  - verify admin access still keys off Django superuser
- If touching uploads/chat:
  - preserve behavior where upload extraction is separate from message persistence
- Run relevant tests and smoke-check key pages (`/agents/`, `/prompts/`, `/agent-admin/`, `/prompt-import/`).
