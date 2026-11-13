"""Cliente del asistente. Con DEEPSEEK_API_KEY habla con DeepSeek; si no, con Anthropic."""

from app.assistant.prompt import for_provider
from app.settings import settings

DEEPSEEK_BASE = "https://api.deepseek.com/anthropic"


def has_model() -> bool:
    return bool(settings.deepseek_api_key or settings.anthropic_api_key)


def uses_deepseek() -> bool:
    return bool(settings.deepseek_api_key)


def assistant_client():
    import anthropic

    if settings.deepseek_api_key:
        return anthropic.Anthropic(api_key=settings.deepseek_api_key, base_url=DEEPSEEK_BASE)
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return None


def call_kwargs(request: dict, *, max_tokens: int, tools=None) -> dict:
    prepared = for_provider(request, deepseek=uses_deepseek())
    kwargs = {
        "model": settings.assistant_answer_model,
        "max_tokens": max_tokens,
        "system": prepared["system"],
        "messages": prepared["messages"],
    }
    # El modo thinking viene encendido y rompe el ciclo de herramientas.
    if uses_deepseek():
        kwargs["thinking"] = {"type": "disabled"}
    if tools:
        kwargs["tools"] = tools
    return kwargs
