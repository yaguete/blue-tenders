"""Resumen diario o semanal. No manda un correo vacío y no repite una baja."""

import argparse
from datetime import UTC, datetime

from app.alerts.send import deliver, due_reminders, new_since
from app.store import get_store


def _messages(store, cadence: str) -> list[dict]:
    data = store.load()
    suppressed = {row.get("id") for row in data.get("suppressions") or []}
    items = store.opportunities()
    messages = []
    now = datetime.now(UTC).isoformat()
    for alert in data.get("alerts") or []:
        if alert.get("cadence") != cadence or alert.get("id") in suppressed:
            continue
        fresh = new_since(items, alert)
        moved = [
            row
            for row in store.recent_history()
            if row.get("field") == "deadline_at"
            and any(
                saved.get("opportunity_id") == row.get("opportunity_id")
                and saved.get("user_id") == alert.get("user_id")
                for saved in data.get("saved") or []
            )
        ]
        if not fresh and not moved:
            alert["last_sent_at"] = now
            continue
        lines = [f"- {item.title_en or item.title}" for item in fresh]
        lines += [
            f"- deadline moved: {row.get('old_value')} -> {row.get('new_value')}" for row in moved[:10]
        ]
        messages.append(
            {
                "email": alert["email"],
                "subject": "Calls matching your search",
                "text": "\n".join(lines),
                "unsubscribe_url": f"https://localhost/alerts/unsubscribe?id={alert['id']}&token={alert.get('unsubscribe_token', '')}",
            }
        )
        alert["last_sent_at"] = now
    for note in due_reminders(data.get("saved") or [], items):
        if not note.get("email"):
            continue
        messages.append(
            {
                "email": note["email"],
                "subject": f"Deadline in {note.get('days', '')} days".strip(),
                "text": note.get("title") or "",
                "unsubscribe_url": "https://localhost/alerts/unsubscribe",
            }
        )
    store.save(data)
    return messages


def run(cadence: str) -> str:
    store = get_store()
    messages = _messages(store, cadence)
    if not messages:
        print(f"[alerts] {cadence}: nothing to send")
        return "empty"
    return deliver(messages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--digest", choices=["daily", "weekly"], required=True)
    args = parser.parse_args()
    run(args.digest)


if __name__ == "__main__":
    main()
