"""Build system prompt blocks for personalized chat responses.

Pure helpers — no Django model imports here. Callers fetch agents,
agent prompts, and users from the DB and pass the resulting objects
(or None) into these functions.
"""

# ── Personalization mappings ────────────────────────────────────────

_COMPANY_SIZE_PHRASE = {
    "solo": "as a solo operator",
    "2-10": "at a 2–10 person company",
    "11-50": "at an 11–50 person company",
    "51-200": "at a 51–200 person company",
    "200+": "at a company with 200+ people",
}

_COMMUNICATION_STYLE = {
    "direct": "Be direct and to the point.",
    "friendly": "Use a warm, friendly tone.",
    "formal": "Use a formal, professional tone.",
    "casual": "Use a casual, conversational tone.",
}

_RESPONSE_LENGTH = {
    "concise": "Keep responses brief — answer in as few words as possible.",
    "balanced": "Use moderate-length responses with relevant detail.",
    "detailed": "Provide thorough, detailed responses with full context.",
}

_EXPERTISE_LEVEL = {
    "beginner": "Assume limited prior knowledge — explain terms and concepts.",
    "intermediate": "Assume working familiarity with the topic — skip basics.",
    "expert": "Assume deep expertise — be precise and skip introductory framing.",
}

_FORMALITY = {
    1: "Use very casual language — contractions, informal phrasing.",
    2: "Use casual language.",
    4: "Use formal language.",
    5: "Use very formal, business-grade language.",
    # 3 is the neutral default — treated as no explicit preference, omitted.
}

_EMOJI_USE = {
    "never": "Do not use emojis.",
    "sparingly": "Use emojis sparingly — at most one per response when it adds clarity.",
    "freely": "Use emojis when they add warmth or clarity.",
}

_PUSHBACK_STYLE = {
    "always": "Push back when the user is wrong — correct mistakes directly without softening.",
    "diplomatic": "When the user is wrong, point it out diplomatically with reasoning.",
    "supportive": "When the user is wrong, acknowledge what they got right before identifying issues.",
}

_EXPLANATION_STYLE = {
    "answer_only": "Give the answer without explanation unless asked.",
    "with_reasoning": "Explain your reasoning alongside answers.",
    "step_by_step": "Walk through your reasoning step by step.",
}

_CLARIFYING_QUESTIONS = {
    "when_needed": "Ask clarifying questions only when needed.",
    "always": "Confirm intent with a clarifying question before answering.",
    "never": "Never ask clarifying questions — make reasonable assumptions and answer.",
}

DEFAULT_BASE_CONTEXT = "You are a practical assistant for SMB users."

_PERSONALIZATION_HEADER = (
    "User personalization (apply to your responses naturally — "
    "these are preferences, not rigid rules):"
)


def build_agent_identity_prompt(agent, agent_prompts) -> str:
    """Construct an agent identity block from an Agent and its AgentPrompt rows.

    `agent` may be None (free-form chat with no matching agent record).
    `agent_prompts` is an iterable of AgentPrompt-like objects with
    `prompt_type` and `content` attributes. May be empty.
    """
    if agent is None:
        return ""

    name = (getattr(agent, "name", "") or "").strip()
    description = (getattr(agent, "description", "") or "").strip()

    head = f"You are {name}." if name else ""
    if description:
        head = f"{head} {description}".strip()

    hints, use_cases = [], []
    for p in agent_prompts or []:
        content = (getattr(p, "content", "") or "").strip()
        if not content:
            continue
        kind = getattr(p, "prompt_type", "")
        if kind == "hint":
            hints.append(content)
        elif kind == "use_case":
            use_cases.append(content)

    blocks = []
    if head:
        blocks.append(head)
    if hints:
        blocks.append(
            "Typical short user queries:\n"
            + "\n".join(f"- {h}" for h in hints)
        )
    if use_cases:
        blocks.append(
            "Examples of detailed user requests:\n"
            + "\n".join(f"- {u}" for u in use_cases)
        )

    return "\n\n".join(blocks)


def build_user_personalization_prompt(user) -> str:
    """Construct a personalization block from the user's profile fields.

    `user` may be None or any object exposing the profile attributes.
    Returns "" if no meaningful fields are filled. Bullets are grouped
    into four sub-sections; empty sub-sections are omitted entirely.
    """
    if user is None:
        return ""

    about_lines = []
    comm_lines = []
    behavior_lines = []
    context_lines = []

    # ── About the user ──
    display_name = (getattr(user, "display_name", "") or "").strip()
    if display_name:
        about_lines.append(
            f'- Address them as "{display_name}" when greeting and at natural '
            "moments — not in every response."
        )

    role = (getattr(user, "role", "") or "").strip()
    if role:
        about_lines.append(f"- Their job title: {role}.")

    industry = (getattr(user, "industry", "") or "").strip()
    if industry:
        about_lines.append(f"- They work in the {industry} industry.")

    company_size = (getattr(user, "company_size", "") or "").strip()
    if company_size in _COMPANY_SIZE_PHRASE:
        about_lines.append(f"- They work {_COMPANY_SIZE_PHRASE[company_size]}.")

    years_exp = (getattr(user, "years_experience", "") or "").strip()
    if years_exp:
        years_phrase = "less than 1 year" if years_exp == "<1" else f"{years_exp} years"
        about_lines.append(f"- They have {years_phrase} of experience.")

    timezone = (getattr(user, "timezone", "") or "").strip()
    if timezone:
        about_lines.append(f"- Their timezone is {timezone}.")

    expertise_areas = getattr(user, "expertise_areas", None) or []
    if isinstance(expertise_areas, list):
        cleaned = [str(a).strip() for a in expertise_areas if str(a).strip()]
        if cleaned:
            about_lines.append(f"- Their expertise areas: {', '.join(cleaned)}.")

    # ── Communication preferences ──
    cs = (getattr(user, "communication_style", "") or "").strip()
    if cs in _COMMUNICATION_STYLE:
        comm_lines.append(f"- {_COMMUNICATION_STYLE[cs]}")

    rl = (getattr(user, "response_length", "") or "").strip()
    if rl in _RESPONSE_LENGTH:
        comm_lines.append(f"- {_RESPONSE_LENGTH[rl]}")

    el = (getattr(user, "expertise_level", "") or "").strip()
    if el in _EXPERTISE_LEVEL:
        comm_lines.append(f"- {_EXPERTISE_LEVEL[el]}")

    formality = getattr(user, "formality", None)
    if formality in _FORMALITY:  # 3 deliberately not in the map
        comm_lines.append(f"- {_FORMALITY[formality]}")

    eu = (getattr(user, "emoji_use", "") or "").strip()
    if eu in _EMOJI_USE:
        comm_lines.append(f"- {_EMOJI_USE[eu]}")

    # ── How to handle disagreement and reasoning ──
    pb = (getattr(user, "pushback_style", "") or "").strip()
    if pb in _PUSHBACK_STYLE:
        behavior_lines.append(f"- {_PUSHBACK_STYLE[pb]}")

    es = (getattr(user, "explanation_style", "") or "").strip()
    if es in _EXPLANATION_STYLE:
        behavior_lines.append(f"- {_EXPLANATION_STYLE[es]}")

    cq = (getattr(user, "clarifying_questions", "") or "").strip()
    if cq in _CLARIFYING_QUESTIONS:
        behavior_lines.append(f"- {_CLARIFYING_QUESTIONS[cq]}")

    # ── Current context ──
    current_focus = (getattr(user, "current_focus", "") or "").strip()
    if current_focus:
        context_lines.append(f"- Their current focus: {current_focus}")

    things_to_avoid = (getattr(user, "things_to_avoid", "") or "").strip()
    if things_to_avoid:
        context_lines.append(f"- Avoid the following entirely: {things_to_avoid}")

    about_me = (getattr(user, "about_me", "") or "").strip()
    if about_me:
        context_lines.append(
            f"- Background and preferences (let this shape your tone and format): {about_me}"
        )

    sections = []
    if about_lines:
        sections.append("About the user:\n" + "\n".join(about_lines))
    if comm_lines:
        sections.append("Communication preferences:\n" + "\n".join(comm_lines))
    if behavior_lines:
        sections.append(
            "How to handle disagreement and reasoning:\n" + "\n".join(behavior_lines)
        )
    if context_lines:
        sections.append("Current context:\n" + "\n".join(context_lines))

    if not sections:
        return ""

    return _PERSONALIZATION_HEADER + "\n\n" + "\n\n".join(sections)


def build_full_system_prompt(agent, agent_prompts, user, base_context=DEFAULT_BASE_CONTEXT) -> str:
    """Compose the complete system prompt for a chat send.

    Order:
      1. Agent identity block (if agent given)
      2. Base context (always present as a floor)
      3. User personalization block (if any fields are filled)

    Empty blocks omitted; remaining blocks joined by "\\n\\n".
    """
    blocks = []

    agent_block = build_agent_identity_prompt(agent, agent_prompts)
    if agent_block:
        blocks.append(agent_block)

    blocks.append(base_context)

    personalization_block = build_user_personalization_prompt(user)
    if personalization_block:
        blocks.append(personalization_block)

    return "\n\n".join(blocks)
