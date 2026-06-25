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
- `createsuperuser` is required to access `/admin-dashboard/` and `/prompt-import/`.
- Keep migrations scoped to `myApp` unless intentionally changing other apps.

## Build Phase Status

Completed phases: 1a, 1b, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, B+F, G
Remaining phases: none — admin dashboard build complete; launch sprint (email + onboarding) shipped; agent avatars shipped

Phase summary:
- **1a/1b** — Auth (CustomUser, session), core pages, shared.css design system
- **2** — Agent catalog + chat runtime
- **3** — Prompts library
- **4** — User profile + AI personalization system
- **5** — Billing page
- **6** — Admin dashboard shell + Agents CRUD
- **7** — Admin dashboard Prompts CRUD (list + create/edit form with category combobox)
- **8** — Industries CRUD in admin dashboard; `/api/industries` replaces hardcoded `INDUSTRY_OPTIONS`
- **9** — Events CRUD in admin dashboard
- **10** — Banners CRUD in admin dashboard + site-wide banner display. Banners are DB-driven via `/api/banners` with rendering across all 12 authenticated templates. Dismissal is client-side via localStorage with `ban-dismiss-<id>` keys. Stacking with impersonation banner handled by body class composition (`body.impersonating` + `body.has-system-banner`).
- **11** — Admin dashboard: Users section (list, detail, suspend/unsuspend, impersonate, export)
- **12** — Tools CRUD in admin dashboard; `/agent-admin/` removed, all agent management consolidated into `/admin-dashboard/`

### Phase B+F (Launch Sprint — Email + Onboarding)

- Email verification flow (Resend HTTP API integration via `myApp/email_service.py`)
- 8 new `CustomUser` fields: `email_verified`, `email_verification_token`, `email_verification_sent_at`, `onboarding_completed`, `onboarding_industry`, `onboarding_use_cases`, `last_lifecycle_email_sent`, `last_lifecycle_email_kind`
- Migration `0006` with data backfill (existing users marked verified + onboarded)
- 3-step onboarding flow (welcome → industry → use cases) with personalized recommendations
- Auto-login on email verification (user proves email control via token)
- `/verify-email-required/` accessible to anonymous users (uses `sessionStorage` fallback)
- Lifecycle emails: day-3 check-in, day-14 strategy call with usage stats + Calendly link
- Cron-ready management command: `send_lifecycle_emails` (idempotent, supports `--dry-run`)
- All 12 authenticated templates carry the `email_verified` + `onboarding_completed` gate snippet
- `OPENAI_API_KEY` loaded via `python-dotenv` in `settings.py`

### Phase G (Agent Avatars — Photoreal Portraits)

- New `Agent.avatar_url` field (URLField, blank-default) — migration `0007`
- `gpt-image-1` portrait generation with industry-conditional backdrop and deterministic 50/50 gender split (see `AI Agent Avatar System` section below for the full design)
- Cloudinary upload to `aikonik/agent_avatars/` (separate folder + separate upload helper from chat-upload `_upload_to_cloudinary`)
- Generation runs **after** `Agent.objects.create` and **outside** the `transaction.atomic()` block — slow image API never holds the DB lock; failures leave `avatar_url=""` and the UI falls back to `icon_class`
- New endpoint: `POST /api/admin/agents/<id>/regenerate-avatar` (admin-gated, audit-logged as `agent.regenerate_avatar`)
- Admin dashboard agent edit form has an Avatar card with a Regenerate button (visible only in edit mode; create mode shows a "will be generated on save" hint)
- Hero-cover layout in `agents.html` (full-bleed 1:1 cover with overlaid name + featured badge); avatar surfaced in chat header, info panel, agent picker, admin row, admin live preview
- Backfill management command: `python manage.py backfill_agent_avatars` (`--dry-run`, `--force`, `--limit N`); idempotent — default mode only fills missing avatars

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
- Protected areas: `/admin-dashboard/`, `/prompt-import/`, all `/api/admin/*`.

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

### 3) Admin Dashboard Architecture

The primary admin UI is the SPA at `/admin-dashboard/` (`admin-dashboard.html`).

Sections (sidebar navigation):
- **PULSE** — platform stats, recent activity
- **USERS** — list, detail, suspend/unsuspend, impersonate, CSV export
- **CONTENT**
  - Agents — full CRUD (Phase 6)
  - Prompts — full CRUD (Phase 7)
  - Industries — full CRUD (Phase 8)
  - Events — full CRUD (Phase 9)
  - Tools — full CRUD (Phase 12)
  - Banners — full CRUD (Phase 10); site-wide display via `applyActiveBanners()` injected into all 12 authenticated templates
- **OPERATIONS** — Summary, Token Usage, Audit Log, Error Log

Dual admin role:
- `/admin-dashboard/*` — primary admin UI for all ongoing content/user management
- `/prompt-import/` — special-purpose bulk CSV/XLSX import tool; kept separate because it handles large file uploads with a dedicated UX

`/agent-admin/` has been **removed** (Phase 12). All agent management is now in `/admin-dashboard/content/agents/`.

Key architecture notes:
- **Audit log privacy**: `record_admin_action` stores field NAMES only, never field values.
- **Impersonation**: sets `impersonating_user_id` + `impersonation_expires` (30-min TTL) in session; `get_current_user` swaps identity transparently; `api_admin_stop_impersonation` clears both keys.
- **`INDUSTRY_OPTIONS`**: hardcoded constant in `admin-dashboard.html` with a `// TODO Phase 8` comment — will be replaced by `/api/industries` when Phase 8 lands.
- **Prompt category combobox**: fetches from `/api/admin/prompts/categories` (distinct values from DB, cached client-side in `peCategoryCache`). Free-text entry also allowed — typed value saves as-is.
- **`accent_bg` hex validator**: in `api_admin_agent_detail` PATCH, `accent_bg` is validated against `/^#[0-9a-fA-F]{3,8}$/` before save.
- **SPA routing**: `navigateTo(path, section, params)` + `showSection(key, params)` handle all panel switches and URL pushState.

### 4) Agents / Prompts Data Model

Two related domains:
- `Prompt` / `SavedPrompt`: library shown on `/prompts/`
  - admin bulk import via `api_admin_import_prompts` (`/prompt-import/`)
  - supports CSV/XLSX ingestion and header normalization (`HEADER_ALIASES`)
  - managed one-by-one via `/admin-dashboard/content/prompts/`
  - `category` field: free-form hierarchical string (94 distinct values in seed data); tags from bulk import are embedded in `body` as `[Tags: ...]` — there is no separate tags field
  - `saved_count` is a computed annotation (`Count('saved_by')`), not a model field; serializer uses `getattr(prompt, "saved_count", 0)` to handle non-annotated queries
- `Agent` / `AgentPrompt`: agent catalog and attached prompts
  - managed via `/admin-dashboard/content/agents/`
  - delivered to UI via `/api/agents`

Seeding behavior:
- Seeding is on-demand in request flow (not migration-driven).
- `ensure_seed_prompts()` and `ensure_seed_agents()` short-circuit when data already exists.
- Do not call seed functions from endpoints that should be strictly read-only/non-mutating.

Input normalization:
- Use `INDUSTRY_MAP` (`views.py`) for free-text industry normalization.

### 5) Environment Loading

`myProject/settings.py` calls `python-dotenv`'s `load_dotenv()` at startup to pull values from a repo-root `.env` file into `os.environ` before any Django setting is read. This is how `OPENAI_API_KEY`, `DJANGO_SECRET_KEY`, `DEBUG`, `DATABASE_URL`, and the Cloudinary credentials reach the app in local dev. In Railway and other hosted envs, real env vars take precedence — `load_dotenv()` is a no-op when `.env` is absent. Add new secrets to `.env` (and to the deployment env) rather than committing them.

### 6) Chat Runtime Flow

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

## AI Personalization System

The chat system prompt is built dynamically per request from three sources, in this order:

1. **Agent identity** (`myApp/personalization.py` — `build_agent_identity_prompt`)
   - Pulled from the `Agent` table via `session.agent_name` lookup
   - Includes agent name, description, hint prompts (framed as "Typical short user queries"), use_case prompts (framed as "Examples of detailed user requests")
   - Skipped if no matching `Agent` row

2. **Base context line** (`"You are a practical assistant for SMB users."`)
   - Always present — `DEFAULT_BASE_CONTEXT` in `personalization.py`
   - The floor everything else builds on

3. **User personalization** (`build_user_personalization_prompt`)
   - 18 `CustomUser` profile fields mapped to actionable instructions
   - Grouped into 4 sub-sections: About the user / Communication preferences / How to handle disagreement and reasoning / Current context
   - Empty fields and empty sub-sections omitted entirely
   - Skipped if user has no fields filled

Composition lives in `build_full_system_prompt`. View integration is at the top of `api_send_chat_message` in `views.py` — agent + agent_prompts fetched fresh per request so profile and agent edits propagate immediately.

API surface:
- `GET /api/profile` — current user's 18 personalization fields
- `PUT /api/profile` — validates against choice whitelists, length caps, `expertise_areas` whitelist, normalizes industry via `INDUSTRY_MAP`. Returns `{"errors": {...}}` on 400.
- `/api/auth/me` intentionally **not** extended with profile fields (would bloat every page load)

When editing chat behavior or adding profile fields:
- `personalization.py` is pure — no Django imports, fully unit-testable
- New profile field requires: model field + migration + form section in `profile.html` + mapping in `personalization.py` + entry in `build_user_personalization_prompt`
- Token cost ~440 tokens per request for fully-filled profile + agent — acceptable for now, caching strategy on `ChatSession` is the future optimization if needed

## AI Agent Avatar System

Photoreal upper-body portraits for every agent, generated on demand via OpenAI Images and stored on Cloudinary. The whole pipeline is **best-effort**: every failure path leaves `avatar_url=""` so the existing `icon_class` keeps rendering.

### Pipeline (where it lives)

1. **Prompt assembly** — `myApp/openai_service.py::_build_avatar_prompt(name, industry, description, tag)`
   composes: subject line → industry backdrop → locked style suffix.
2. **Image generation** — `generate_agent_avatar_bytes(...)` calls `client.images.generate(model="gpt-image-1", size="1024x1024", n=1)` and decodes `b64_json`. Returns `None` on any failure (no API key, network, content policy). **Never raises.**
3. **Cloudinary upload** — `myApp/views.py::_upload_avatar_to_cloudinary(image_bytes, slug)` uploads as `resource_type="image"` (NOT `"raw"` — that's the chat-upload helper) under `aikonik/agent_avatars/<slug>-<uuid8>.png`.
4. **Persist** — `_generate_and_store_agent_avatar(agent)` orchestrates 1→2→3, sets `agent.avatar_url`, saves with `update_fields=["avatar_url", "updated_at"]`.

### The prompt is built from three pieces

- **Subject line** (per-agent): name, role (tag + industry), description snippet (capped 280 chars), gender hint, "this is an AI assistant rendered as a real human, not a robot."
- **Industry backdrop** — `INDUSTRY_BACKDROP_MAP` in `openai_service.py` keyed on a normalized industry slug (lowercase + alphanumerics only, so `"real estate"`, `"REAL-ESTATE"`, `"realestate"` all collapse to `realestate`). Misses fall through to `DEFAULT_INDUSTRY_BACKDROP`. Covers 12 industries (legal, healthcare, finance, marketing, technology, realestate, accounting, logistics, manufacturing, education, hospitality, retail). Each entry describes a **recognizable but softly blurred** environment — the f/2.2 aperture is intentional so the backdrop reads.
- **Locked style suffix** — `AGENT_AVATAR_STYLE_SUFFIX`. Photoreal upper-body hero composition, 85mm @ f/2.2, warm key + cool ambient, "no extra people in frame." Editing this changes every NEWLY generated avatar; existing stored URLs are not retroactively re-rendered (regeneration required).

### Bias mitigation: deterministic 50/50 gender split

`_resolve_gender_presentation(name)` hashes `agent.name` with SHA-256 and uses the low byte's parity for the woman/man split. This is intentional, not a workaround:
- **Why hash**: `gpt-image-1` skews heavily male on prompts containing "executive," "confident," "authority," "premium business team." A soft "vary gender presentation" instruction was empirically not enough — testing showed every avatar generated as male.
- **Why deterministic**: the Regenerate button in admin would otherwise randomly flip a "Maria" agent into a man between rolls. Hashing on the stable `name` means re-rolls produce the same gender for the same agent.
- **Why `name` and not `slug`**: both change together (slug derives from name), so they're equivalent for stability. `name` is already in scope; using it avoids extra plumbing.
- **Distribution**: ~50/50 by construction. The current 9-agent catalog landed at 6/3 — that's normal small-sample variance, not a bug.

### How regeneration works

- API: `POST /api/admin/agents/<agent_id>/regenerate-avatar` (admin-gated, audit-logged as `agent.regenerate_avatar`).
- UI: button in the Avatar card inside the admin agent edit form. Disabled in create mode (the agent has no ID yet — generation happens automatically after the create POST returns).
- The endpoint always replaces `avatar_url` in place. Cloudinary `overwrite=False` + a UUID suffix means each generation is a fresh asset (good for cache invalidation across CDNs).
- Regeneration costs ~$0.04 per call (`gpt-image-1` standard 1024×1024). One-time per agent under normal use.

### Backfill command

`python manage.py backfill_agent_avatars` — generates avatars for agents that don't have one. Defaults are idempotent (re-running is a no-op once the catalog is filled).

- `--dry-run` — list eligible agents without touching OpenAI/Cloudinary
- `--force` — regenerate every agent, including those with an existing `avatar_url` (use after editing `AGENT_AVATAR_STYLE_SUFFIX` or `INDUSTRY_BACKDROP_MAP` to apply changes to existing rows)
- `--limit N` — process at most N agents (use for trial runs before committing to a full re-roll)

### Where avatars surface in the UI (with `icon_class` fallback everywhere)

- `agents.html` — full-bleed 1:1 hero cover at top of each agent card with name + featured badge overlaid; the Featured-this-week banner uses the avatar in a 38%-width portrait zone with a gradient blend into the content panel.
- `agent-chat.html` — chat header, info panel inline, agent picker cards.
- `admin-dashboard.html` — agent list row icon cell, edit form Avatar card with regenerate button, Live Preview card.

When editing avatar logic:
- The two Cloudinary helpers (`_upload_to_cloudinary` for chat uploads, `_upload_avatar_to_cloudinary` for avatars) are intentionally separate — chat uploads use `resource_type="raw"` for arbitrary file types; avatars use `resource_type="image"` so Cloudinary applies image-specific optimizations.
- Generation must stay **outside** the `transaction.atomic()` block in agent create — a 5–15s API call holding a DB lock would be a real problem under concurrent admin edits.
- All UI surfaces follow the same fallback contract: if `agent.avatar_url` is truthy and looks like an http(s) URL, render `<img>`; otherwise render the FontAwesome `icon_class`. Don't add a third visual state — keep the binary.

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

## Design System Notes

- All authenticated app pages use `class="dark-app"` on `<body>` and rely on `shared.css` for theme.
- Auth pages (login, register) use `class="auth-layout"` on `<body>`.
- Public landing page (`index.html`) and bulk import (`prompt-import.html`) use `shared.css` with no body class — they remain light-themed.
- `admin-dashboard.html` uses `shared.css` with `class="dark-app"` — it is part of the main app theme.

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
  - keep `_upload_to_cloudinary` (raw) and `_upload_avatar_to_cloudinary` (image) as separate helpers — they target different folders and use different `resource_type`
- If touching agent avatars:
  - keep the icon_class fallback intact in every render site (cards, chat header, agent picker, admin row, admin live preview)
  - keep `_generate_and_store_agent_avatar` outside any `transaction.atomic()` block — image-API latency must not hold a DB lock
  - if you change `AGENT_AVATAR_STYLE_SUFFIX` or `INDUSTRY_BACKDROP_MAP`, run `python manage.py backfill_agent_avatars --force` to apply to existing rows (or accept that they stay on the old style until manually regenerated)
- Run relevant tests and smoke-check key pages (`/agents/`, `/prompts/`, `/admin-dashboard/`, `/prompt-import/`).
