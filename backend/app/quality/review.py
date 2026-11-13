"""Cola de revisión en memoria, persistida junto al almacén JSON."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.opportunity import Opportunity


def review_item(
    opp: Opportunity,
    reason: str,
    field: str | None = None,
    detail: str | None = None,
) -> dict:
    return {
        "id": uuid4().hex[:12],
        "opportunity_id": opp.id,
        "reason": reason,
        "field": field,
        "detail": detail,
        "created_at": datetime.now(UTC).isoformat(),
        "resolved": False,
    }
