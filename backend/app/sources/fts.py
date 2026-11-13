"""Find a Tender (Reino Unido). API OCDS, Open Government Licence.

No está en el cron: primero hay que medir cuántos anuncios del sector salen en 90 días.
"""

from collections.abc import Iterable
from datetime import date, datetime

import httpx

from app.models.opportunity import Budget, Opportunity, OpportunityType
from app.sources.base import Source
from app.vertical import Vertical

SEARCH_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"


class FtsSource(Source):
    id = "fts"
    kind = "api"

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del vertical
        with httpx.Client(timeout=40) as client:
            response = client.get(SEARCH_URL, params={"updatedFrom": since.isoformat(), "limit": 100})
            response.raise_for_status()
            payload = response.json()
        yield from payload.get("releases") or []

    def to_tender(self, raw: dict) -> Opportunity:
        tender = raw.get("tender") or {}
        ocid = str(raw.get("ocid") or "")
        title = tender.get("title")
        if not ocid or not title:
            raise ValueError("anuncio de Find a Tender sin ocid o sin título")
        period = (tender.get("tenderPeriod") or {}).get("endDate")
        amount = ((tender.get("value") or {}).get("amount"))
        currency = (tender.get("value") or {}).get("currency") or "GBP"
        budget = None
        if amount is not None:
            budget = Budget(amount=float(amount), currency=currency, amount_eur=float(amount) if currency == "EUR" else None)
        return Opportunity(
            id=Opportunity.make_id(self.id, ocid),
            source_id=self.id,
            external_id=ocid,
            url=f"https://www.find-tender.service.gov.uk/Notice/{ocid}",
            type=OpportunityType.tender,
            title=str(title),
            description=tender.get("description"),
            country="GB",
            language="en",
            budget=budget,
            deadline_at=datetime.fromisoformat(period) if period else None,
            raw=raw,
        )
