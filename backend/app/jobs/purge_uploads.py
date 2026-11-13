"""Borra las subidas del asistente pasadas 24 horas.

uv run python -m app.jobs.purge_uploads
"""

from datetime import UTC, datetime

from app.store import get_store


def main() -> None:
    gone = get_store().purge_expired_uploads(datetime.now(UTC))
    print(f"[uploads] purged {gone}")


if __name__ == "__main__":
    main()
