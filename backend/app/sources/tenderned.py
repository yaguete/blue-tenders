"""TenderNed. API JSON pública del listado, no el feed ATOM.

El feed solo trae unas horas de avisos: un cron diario perdería más de la mitad.
`europees` true significa que el aviso también va a TED y no se ingiere.
"""

from collections.abc import Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from app.models.opportunity import Buyer, Opportunity, OpportunityType
from app.sources.base import SOURCE_SUBSECTORS, Source
from app.sources.terms import search_pairs
from app.vertical import Vertical

SEARCH_URL = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"
_ZONE = ZoneInfo("Europe/Amsterdam")


def tenderned_keep(raw: dict) -> str:
    """`eu` (también va a TED), `pin`, `keep` o `skip` (adjudicación o baja)."""
    label = str((raw.get("typePublicatie") or {}).get("omschrijving") or "").lower()
    if raw.get("isVroegtijdigeBeeindiging") is True:
        return "skip"
    if any(word in label for word in ("gegund", "gunning")):
        return "skip"
    if raw.get("europees") is True:
        return "eu"
    if "vooraankondiging" in label:
        return "pin"
    return "keep"


def _deadline(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_ZONE)
    return parsed


class TendernedSource(Source):
    id = "tenderned"
    kind = "api"
    volume_alert = False

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        pairs = search_pairs(vertical, self.id)
        if not pairs:
            raise ValueError("TenderNed: el vertical no tiene search_terms.tenderned.")
        self.skipped_eu = 0
        seen: dict[str, dict] = {}
        with httpx.Client(timeout=40, headers={"User-Agent": "blue-tender/1.0", "Accept": "application/json"}) as client:
            for subsector, term in pairs:
                page = 0
                while page < 30:
                    response = client.get(
                        SEARCH_URL,
                        params={
                            "page": page,
                            "size": 50,
                            "search": term,
                            "publicatieDatumVanaf": since.isoformat(),
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    rows = payload.get("content") or []
                    for row in rows:
                        published = str(row.get("publicatieDatum") or "")[:10]
                        if published and published < since.isoformat():
                            continue
                        decision = tenderned_keep(row)
                        ident = str(row.get("publicatieId") or "")
                        if decision == "skip" or not ident:
                            continue
                        if ident in seen:
                            found = seen[ident].setdefault(SOURCE_SUBSECTORS, [])
                            if subsector not in found:
                                found.append(subsector)
                            continue
                        row = dict(row)
                        if decision == "eu":
                            row["_skip_eu"] = True
                        if decision == "pin":
                            row["_pin"] = True
                        row[SOURCE_SUBSECTORS] = [subsector]
                        seen[ident] = row
                    if payload.get("last") or not rows:
                        break
                    page += 1
        yield from seen.values()

    def to_tender(self, raw: dict) -> Opportunity:
        ident = str(raw.get("publicatieId") or "")
        title = raw.get("aanbestedingNaam")
        if not ident or not title:
            raise ValueError("anuncio de TenderNed sin id o sin título")
        link = raw.get("link") or {}
        url = link.get("href") if isinstance(link, dict) else None
        buyer = raw.get("opdrachtgeverNaam")
        published = str(raw.get("publicatieDatum") or "")[:10]
        return Opportunity(
            id=Opportunity.make_id(self.id, ident),
            source_id=self.id,
            external_id=ident,
            url=url or f"https://www.tenderned.nl/aankondigingen/overzicht/{ident}",
            type=OpportunityType.prior_information_notice if raw.get("_pin") else OpportunityType.tender,
            title=str(title),
            description=raw.get("opdrachtBeschrijving"),
            buyer=Buyer(name=str(buyer), country="NL") if buyer else None,
            country="NL",
            language="nl",
            published_at=date.fromisoformat(published) if published else None,
            deadline_at=_deadline(raw.get("sluitingsDatum")),
            raw=raw,
        )
