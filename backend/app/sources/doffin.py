"""Doffin (Noruega).

La búsqueda pública es `GET /public/v2/search` (clave en Profile, no en la ficha
del endpoint). Sin `DOFFIN_API_KEY` se usa la API interna de la web.
`sentToTed` true no se ingiere. El listado público no trae plazo: eso está en
`GET /public/v2/download/{id}`, 10 peticiones por minuto.
"""

import time
from collections.abc import Iterable
from datetime import date, datetime

import httpx

from app.models.opportunity import Budget, Buyer, Opportunity, OpportunityType
from app.settings import settings
from app.sources.base import SOURCE_SUBSECTORS, Source
from app.sources.terms import search_pairs
from app.vertical import Vertical

PUBLIC_URL = "https://api.doffin.no/public/v2/search"
INTERNAL_URL = "https://api.doffin.no/webclient/api/v2/search-api/search"
_NOTICE_TYPES = ("COMPETITION", "ANNOUNCEMENT_OF_COMPETITION", "PRE_ANNOUNCEMENT")
_RESULTS = {
    "RESULT",
    "ANNOUNCEMENT_OF_CONCLUSION_OF_CONTRACT",
    "CHANGE_OF_CONCLUSION_OF_CONTRACT",
    "CANCELLED_OR_MISSING_CONCLUSION_OF_CONTRACT",
}


def public_params(since: date, term: str, page: int) -> list[tuple[str, str | int]]:
    """Query del GET documentado. `type` se repite: la API no admite una lista."""
    params: list[tuple[str, str | int]] = [
        ("numHitsPerPage", 100),
        ("page", page),
        ("sortBy", "PUBLICATION_DATE_DESC"),
        ("searchString", term),
        ("issueDateFrom", since.isoformat()),
    ]
    params.extend(("type", kind) for kind in _NOTICE_TYPES)
    return params


def _hits(payload: dict) -> list[dict]:
    rows = payload.get("hits") or payload.get("content") or []
    if isinstance(rows, dict):
        return [rows]
    return [row for row in rows if isinstance(row, dict)]


def doffin_keep(raw: dict) -> str:
    if raw.get("sentToTed") is True:
        return "eu"
    kinds = set(raw.get("allTypes") or [])
    if raw.get("type"):
        kinds.add(raw["type"])
    if kinds & _RESULTS:
        return "skip"
    if "PRE_ANNOUNCEMENT" in kinds or raw.get("type") == "PRE_ANNOUNCEMENT":
        return "pin"
    return "keep"


def _public_get(client: httpx.Client, url: str, params: list[tuple[str, str | int]]) -> httpx.Response:
    """30 peticiones por minuto. Un 429 espera lo que diga Retry-After."""
    last = "sin respuesta"
    for attempt in range(4):
        if attempt:
            time.sleep(2 * attempt)
        response = client.get(url, params=params)
        if response.status_code != 429:
            response.raise_for_status()
            time.sleep(2)
            return response
        last = response.headers.get("Retry-After") or "2"
        try:
            time.sleep(min(int(last), 60))
        except ValueError:
            time.sleep(2)
    raise RuntimeError(f"Doffin 429 tras varios intentos (Retry-After {last})")


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class DoffinSource(Source):
    id = "doffin"
    kind = "api"
    volume_alert = False

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        pairs = search_pairs(vertical, self.id)
        if not pairs:
            raise ValueError("Doffin: el vertical no tiene search_terms.doffin.")
        self.skipped_eu = 0
        seen: dict[str, dict] = {}
        public = bool(settings.doffin_api_key)
        if not public:
            print("[doffin] sin DOFFIN_API_KEY: se usa la API interna, provisional")
        headers = {"User-Agent": "blue-tender/1.0"}
        if public:
            headers["Ocp-Apim-Subscription-Key"] = settings.doffin_api_key
        url = PUBLIC_URL if public else INTERNAL_URL
        with httpx.Client(timeout=40, headers=headers) as client:
            for subsector, term in pairs:
                page = 1
                while page <= 20:
                    if public:
                        response = _public_get(client, url, public_params(since, term, page))
                    else:
                        response = client.post(
                            url,
                            json={
                                "numHitsPerPage": 100,
                                "page": page,
                                "searchString": term,
                                "sortBy": "PUBLICATION_DATE_DESC",
                            },
                        )
                        response.raise_for_status()
                    payload = response.json()
                    hits = _hits(payload)
                    for hit in hits:
                        published = str(hit.get("publicationDate") or "")[:10]
                        if published and published < since.isoformat():
                            continue
                        decision = doffin_keep(hit)
                        ident = str(hit.get("id") or "")
                        if decision == "skip" or not ident:
                            continue
                        if ident in seen:
                            found = seen[ident].setdefault(SOURCE_SUBSECTORS, [])
                            if subsector not in found:
                                found.append(subsector)
                            continue
                        hit = dict(hit)
                        if decision == "eu":
                            hit["_skip_eu"] = True
                        if decision == "pin":
                            hit["_pin"] = True
                        hit[SOURCE_SUBSECTORS] = [subsector]
                        seen[ident] = hit
                    total = int(payload.get("numHitsTotal") or payload.get("totalElements") or 0)
                    if not hits or page * 100 >= total:
                        break
                    page += 1
        yield from seen.values()

    def to_tender(self, raw: dict) -> Opportunity:
        ident = str(raw.get("id") or "")
        title = raw.get("heading")
        if not ident or not title:
            raise ValueError("anuncio de Doffin sin id o sin título")
        value = raw.get("estimatedValue") or {}
        amount = value.get("amount") if isinstance(value, dict) else None
        currency = value.get("currencyCode") if isinstance(value, dict) else None
        budget = None
        if amount is not None and currency:
            budget = Budget(
                amount=float(amount),
                currency=str(currency),
                amount_eur=float(amount) if currency == "EUR" else None,
            )
        buyers = raw.get("buyer") or []
        buyer_name = buyers[0].get("name") if buyers and isinstance(buyers[0], dict) else None
        published = str(raw.get("publicationDate") or "")[:10]
        return Opportunity(
            id=Opportunity.make_id(self.id, ident),
            source_id=self.id,
            external_id=ident,
            url=f"https://www.doffin.no/notices/{ident}",
            type=OpportunityType.prior_information_notice if raw.get("_pin") else OpportunityType.tender,
            title=str(title),
            description=raw.get("description"),
            buyer=Buyer(name=str(buyer_name), country="NO") if buyer_name else None,
            country="NO",
            language="no",
            budget=budget,
            published_at=date.fromisoformat(published) if published else None,
            deadline_at=_when(raw.get("deadline")),
            raw=raw,
        )
