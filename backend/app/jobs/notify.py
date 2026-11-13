"""Aviso cuando un trabajo falla, y latido cuando termina bien."""

import httpx

from app.alerts.send import deliver
from app.settings import settings


def report_failure(source: str, message: str) -> None:
    if not settings.ops_email:
        print(f"[notify] {source}: {message}")
        return
    deliver(
        [
            {
                "email": settings.ops_email,
                "subject": f"blue-tender ingest failed: {source}",
                "text": message[:2000],
                "unsubscribe_url": "https://localhost/alerts/unsubscribe",
            }
        ]
    )


def beat() -> None:
    if not settings.heartbeat_url:
        return
    try:
        httpx.get(settings.heartbeat_url, timeout=15)
    except httpx.HTTPError as exc:
        print(f"[heartbeat] {exc}")
