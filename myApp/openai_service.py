from django.conf import settings
from openai import OpenAI


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
