import base64
import hashlib
import logging

from django.conf import settings
from openai import OpenAI


logger = logging.getLogger(__name__)


HISTORY_TOKEN_BUDGET = 80_000
MAX_REQUEST_TOKENS = 120_000  # gpt-4.1-mini context cap (128k) minus response buffer

# Per-industry backdrop. The agent's industry is normalized (lowercased,
# punctuation stripped) and looked up here; misses fall through to
# DEFAULT_INDUSTRY_BACKDROP. Each entry describes a recognizable but softly
# blurred environment — the subject stays sharp, the backdrop carries the
# industry signal.
INDUSTRY_BACKDROP_MAP = {
    "legal": (
        "Backdrop: a stately law office or modern courthouse atrium with warm "
        "wood paneling, marble columns, leather-bound books on dark shelves, "
        "deep amber accent lighting, soft late-afternoon glow. Authoritative "
        "and timeless."
    ),
    "healthcare": (
        "Backdrop: a clean modern hospital corridor or research-lab interior "
        "with frosted glass walls, soft cool light, hints of medical-grade "
        "equipment out of focus, white and pale-teal palette. Clinical but "
        "human."
    ),
    "finance": (
        "Backdrop: a high-floor financial-district office overlooking a city "
        "skyline at dusk, deep blue tones, faint glow from screens and "
        "pendant lights softly out of focus. Quiet, confident wealth."
    ),
    "marketing": (
        "Backdrop: a creative-agency loft with exposed brick, warm Edison-bulb "
        "string lights, mood-board color accents on the walls, a soft golden "
        "glow. Energetic and brand-forward."
    ),
    "technology": (
        "Backdrop: a sleek modern tech office or server hall with cool blue "
        "and teal LED accents, dark architectural lines, faint screen glow, "
        "minimal industrial textures. Cutting-edge premium-tech atmosphere."
    ),
    "realestate": (
        "Backdrop: an upscale modern interior or rooftop terrace overlooking "
        "the city, floor-to-ceiling windows, golden-hour light, warm timber "
        "and soft cream tones. Architectural and aspirational."
    ),
    "accounting": (
        "Backdrop: a refined executive corner office with dark wood shelving, "
        "hardback books, a banker's-lamp glow, deep navy and warm walnut "
        "tones. Discreet and trusted."
    ),
    "logistics": (
        "Backdrop: a vast distribution center or port terminal at dawn, "
        "industrial scale, warm sodium-lamp light against cool blue ambient, "
        "freight outlines softly out of focus. Operational and dependable."
    ),
    "manufacturing": (
        "Backdrop: a modern advanced-manufacturing floor with polished "
        "concrete, blue-white LED task lighting, precision machinery softly "
        "out of focus, brushed-steel and cobalt accents. High-tech industrial."
    ),
    "education": (
        "Backdrop: a modern university library or seminar room with warm "
        "wood, tall bookshelves, soft natural light through clerestory "
        "windows, calm ochre and sage tones. Scholarly and considered."
    ),
    "hospitality": (
        "Backdrop: an upscale boutique-hotel lobby with brass accents, deep "
        "velvet seating softly out of focus, low warm spotlights, rich "
        "burgundy and champagne tones. Refined and welcoming."
    ),
    "retail": (
        "Backdrop: a premium flagship-retail interior with warm spotlights "
        "on minimalist displays, polished concrete or terrazzo floor, soft "
        "neutral palette with one accent color. Curated and modern."
    ),
}

DEFAULT_INDUSTRY_BACKDROP = (
    "Backdrop: a minimalist premium corporate environment, soft warm-gray "
    "gradient with subtle architectural light, no clutter. Quiet authority."
)


def _resolve_industry_backdrop(industry):
    if not industry:
        return DEFAULT_INDUSTRY_BACKDROP
    key = "".join(ch for ch in industry.lower() if ch.isalnum())
    return INDUSTRY_BACKDROP_MAP.get(key, DEFAULT_INDUSTRY_BACKDROP)


def _resolve_gender_presentation(name):
    """Deterministic 50/50 woman/man split, hashed off the agent name.

    Stable across regenerations as long as the agent isn't renamed, so the
    Regenerate button never randomly flips a "Maria" agent into a man. Re-runs
    of `backfill_agent_avatars --force` produce the same gender per agent.

    Why hash on `name` and not `slug`: both are tied to the agent's identity
    and both change if the admin renames the agent (slug derives from name),
    so they're equivalent for stability. `name` is what's already passed to
    the prompt builder — no extra plumbing needed.
    """
    digest = hashlib.sha256((name or "").encode("utf-8")).digest()
    return "woman" if digest[0] % 2 == 0 else "man"


# Locked global style for every agent avatar. Editing this changes the look
# of every NEWLY generated avatar — it does not retroactively re-render
# stored URLs. Regeneration is required for existing avatars.
AGENT_AVATAR_STYLE_SUFFIX = (
    "Single-subject cinematic portrait. "

    "Framing and posture: upper-body hero composition, slight low camera "
    "angle just below the eye line, subject centered or marginally "
    "off-center. Confident, grounded posture with shoulders relaxed and "
    "square, calm and self-assured presence, direct intelligent gaze into "
    "the lens, approachable expression. The subject must read as premium, "
    "composed, and unmistakably human. "

    "Photography: ultra-realistic, shot on a professional medium-format "
    "camera with an 85mm portrait lens at f/2.2. Sharp focus on the face "
    "and wardrobe, gentle bokeh on the background that still leaves the "
    "environment recognizable. Soft cinematic lighting from one side, "
    "warm key with cool ambient fill, gentle facial shadow shaping. "
    "Natural skin texture, lifelike eyes, subtle pores, believable human "
    "detail. "

    "Wardrobe: premium business or smart-casual that fits the industry "
    "context, in tailored neutral tones — charcoal, navy, deep olive, "
    "beige, cream, soft gray, or muted earth tones. Refined, never loud "
    "or costume-like. "

    "Lighting tone: warm key with cool ambient fill, soft contrast, rich "
    "but not crushed shadows. Cinematic premium feel, like a hero frame "
    "from a high-end SaaS or AI-company brand campaign. "

    "Visual identity: render the exact gender presentation, ethnicity, "
    "and age range specified in the subject line above, treating those "
    "instructions as required, not optional. Vary hairstyle, body type, "
    "and personality naturally. The catalog as a whole should feel like "
    "a diverse modern team — never default to one demographic. "

    "Strict constraints: no cartoon, no illustration, no vector, no anime, "
    "no 3D toy or doll, no exaggerated features, no plastic skin, no "
    "stock-photo look, no sci-fi HUD overlays, no text, no logos, no "
    "watermarks, no extra people in the frame. The subject must read as "
    "a real adult professional photographed in a real environment."
)
AGENT_AVATAR_SIZE = "1024x1024"
AGENT_AVATAR_MODEL = "gpt-image-1"


def _est_tokens(text):
    """Conservative token estimator (~chars / 4). No external deps.

    Slightly over-estimates for English prose; under-estimates for dense
    code/URLs. Trade accuracy for zero dependencies — upgrade to tiktoken
    if billing/accuracy demands it.
    """
    return max(1, len(text or "") // 4)


def trim_history_to_budget(history, system_content, budget=HISTORY_TOKEN_BUDGET):
    """Return the most-recent slice of `history` that fits within the token budget.

    Walks newest → oldest, accumulating cost. Always keeps at least the
    most recent message even if it alone exceeds the budget — let the
    pre-flight check or OpenAI return a clear error rather than silently
    dropping the user's actual question.
    """
    used = _est_tokens(system_content)
    kept = []
    for msg in reversed(history):
        cost = _est_tokens(msg.get("content", ""))
        if used + cost > budget and kept:
            break
        kept.append(msg)
        used += cost
    return list(reversed(kept))


def estimate_messages_tokens(system_content, messages):
    """Estimate total tokens for system prompt + message list."""
    return _est_tokens(system_content) + sum(
        _est_tokens(m.get("content", "")) for m in messages
    )


def get_openai_reply(messages):
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    # Newer OpenAI SDKs support client.responses.create.
    if hasattr(client, "responses"):
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=messages,
            temperature=0.4,
        )
        text = getattr(response, "output_text", "").strip()
        usage = getattr(response, "usage", None)
        total_tokens = 0
        if usage and hasattr(usage, "total_tokens") and usage.total_tokens:
            total_tokens = usage.total_tokens
        if not text:
            text = "I could not generate a response right now."
        return text, total_tokens

    # Backward-compatible path for older SDKs.
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        temperature=0.4,
    )
    text = ""
    if completion.choices and completion.choices[0].message:
        text = (completion.choices[0].message.content or "").strip()
    if not text:
        text = "I could not generate a response right now."
    usage = getattr(completion, "usage", None)
    total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
    return text, total_tokens


def _build_avatar_prompt(name, industry, description, tag):
    role_bits = [b for b in [tag, industry] if b]
    role = ", ".join(role_bits) if role_bits else "business operations"

    desc_snippet = (description or "").strip()
    if len(desc_snippet) > 280:
        desc_snippet = desc_snippet[:280].rsplit(" ", 1)[0] + "..."

    backdrop = _resolve_industry_backdrop(industry)
    gender = _resolve_gender_presentation(name)
    identity_line = (
        f"Show this person as a {gender}. Let the model choose age, ethnicity, "
        f"hairstyle, and exact features naturally — but the gender presentation "
        f"is fixed."
    )

    if desc_snippet:
        subject = (
            f'Portrait of "{name}", an adult professional team member working in {role}. '
            f"{identity_line} "
            f"This person represents an AI-powered business assistant, but should look "
            f"like a real human professional, not a robot or fictional avatar. "
            f"Role context: {desc_snippet}"
        )
    else:
        subject = (
            f'Portrait of "{name}", an adult professional team member working in {role}. '
            f"{identity_line} "
            f"This person represents an AI-powered business assistant, but should look "
            f"like a real human professional, not a robot or fictional avatar."
        )

    return f"{subject}\n\n{backdrop}\n\n{AGENT_AVATAR_STYLE_SUFFIX}"


def generate_agent_avatar_bytes(name, industry, description="", tag=""):
    """Generate an illustrated agent portrait via OpenAI Images.

    Returns raw PNG bytes on success, None on any failure (missing API key,
    network error, content policy rejection). Callers must handle None and
    fall back to icon_class rendering.
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("generate_agent_avatar_bytes: OPENAI_API_KEY not set")
        return None
    prompt = _build_avatar_prompt(name, industry, description, tag)
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.images.generate(
            model=AGENT_AVATAR_MODEL,
            prompt=prompt,
            size=AGENT_AVATAR_SIZE,
            n=1,
        )
        data = getattr(response, "data", None) or []
        if not data:
            return None
        b64 = getattr(data[0], "b64_json", None)
        if not b64:
            return None
        return base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_agent_avatar_bytes failed: %s", exc)
        return None
