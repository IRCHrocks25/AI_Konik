from django.conf import settings
from openai import OpenAI


HISTORY_TOKEN_BUDGET = 80_000
MAX_REQUEST_TOKENS = 120_000  # gpt-4.1-mini context cap (128k) minus response buffer


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
