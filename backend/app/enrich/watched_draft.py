"""Un cambio en una página vigilada se convierte en borrador, con una cita del texto."""

from uuid import uuid4

from app.settings import settings


def draft_change(raw: dict) -> dict:
    quote = _quote(raw.get("text") or "", raw.get("previous") or "")
    return {
        "id": uuid4().hex[:12],
        "opportunity_id": None,
        "reason": "watched_change",
        "field": raw.get("id"),
        "detail": quote,
        "resolved": False,
        "url": raw.get("url"),
        "model": settings.classify_model if settings.anthropic_api_key else "fields",
    }


def _quote(current: str, previous: str) -> str:
    if not previous:
        return current[:400]
    current_words = current.split()
    previous_words = set(previous.split())
    fresh = [word for word in current_words if word not in previous_words]
    text = " ".join(fresh).strip()
    return (text or current)[:400]
