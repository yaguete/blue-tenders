"""Alertas y recordatorios. Sin clave de Resend se escriben en data/outbox."""

import hashlib
import hmac
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.models.opportunity import Opportunity, compute_status
from app.search.query import SearchFilters, search_opportunities


def unsubscribe_token(alert_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), alert_id.encode(), hashlib.sha256).hexdigest()[:32]


def token_matches(alert_id: str, token: str, secret: str) -> bool:
    return hmac.compare_digest(unsubscribe_token(alert_id, secret), token)


def new_since(items: list[Opportunity], alert: dict, today: date | None = None) -> list[Opportunity]:
    filters = SearchFilters(**alert.get("filters") or {}, limit=20)
    found = search_opportunities(items, filters, today)["items"]
    watermark = alert.get("last_sent_at")
    if not watermark:
        return found
    stamp = datetime.fromisoformat(watermark)
    fresh = []
    for item in found:
        created = getattr(item, "published_at", None)
        if created is None:
            fresh.append(item)
            continue
        if datetime.combine(created, datetime.min.time(), tzinfo=UTC) > stamp:
            fresh.append(item)
    return fresh


def due_reminders(saved: list[dict], items: list[Opportunity], today: date | None = None) -> list[dict]:
    today = today or date.today()
    by_id = {item.id: item for item in items}
    notes = []
    for row in saved:
        item = by_id.get(row.get("opportunity_id"))
        if not item or not item.deadline_at:
            continue
        days = (item.deadline_at.date() - today).days
        if days in (14, 3):
            notes.append(
                {
                    "email": row.get("email"),
                    "opportunity_id": item.id,
                    "title": item.title_en or item.title,
                    "days": days,
                    "kind": "deadline",
                }
            )
        if compute_status(item, today).value == "closed" and row.get("status") != "closed":
            notes.append(
                {
                    "email": row.get("email"),
                    "opportunity_id": item.id,
                    "title": item.title_en or item.title,
                    "kind": "status_change",
                }
            )
    return notes


def write_outbox(path: Path, messages: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    existing.extend(messages)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def deliver(messages: list[dict]) -> str:
    from app.settings import settings

    if not messages:
        return "empty"
    if not settings.resend_api_key:
        write_outbox(settings.data_dir / "outbox.json", messages)
        return "outbox"
    import httpx

    for message in messages:
        httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from,
                "to": [message["email"]],
                "subject": message["subject"],
                "text": message["text"],
                "headers": {
                    "List-Unsubscribe": f"<{message['unsubscribe_url']}>",
                },
            },
            timeout=20,
        )
    return "resend"


def reminder_window(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    return today, today + timedelta(days=14)
