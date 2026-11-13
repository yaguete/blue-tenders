"""OCDS compartido por Find a Tender y Contracts Finder.

`updatedFrom` y `publishedFrom` tienen que ir con hora. Una fecha sola devuelve 400.
El API corta con 429 si se pagina seguido: se espera y se reintenta.
"""

import time
from collections.abc import Iterable
from datetime import UTC, date, datetime

import httpx

from app.models.opportunity import Budget, Buyer, Opportunity, OpportunityType
from app.sources.base import Source
from app.vertical import Vertical

_OPEN_TAGS = {"tender", "tenderUpdate", "planning"}
_CANCEL_TAGS = {"tenderCancellation"}
_PAGE_LIMIT = 100
_MAX_PAGES = 400


def release_action(raw: dict) -> str:
    """`keep`, `cancel` (cierra la ficha del mismo ocid) o `skip`."""
    tags = set(raw.get("tag") or [])
    if tags & _CANCEL_TAGS:
        return "cancel"
    if tags & _OPEN_TAGS:
        return "keep"
    return "skip"


def keep_release(raw: dict) -> bool:
    """Licitación o información previa. Adjudicaciones y contratos no entran por aquí."""
    return release_action(raw) == "keep"


def _notice_type(raw: dict) -> OpportunityType:
    tags = set(raw.get("tag") or [])
    if "planning" in tags and not (tags & {"tender", "tenderUpdate"}):
        return OpportunityType.prior_information_notice
    return OpportunityType.tender


def _stamp(day: date) -> str:
    return datetime(day.year, day.month, day.day, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _dates_bite(releases: list[dict], since: date) -> None:
    """Si la página más nueva es anterior a `since`, el filtro de fecha no ha hecho caso."""
    found = []
    for release in releases:
        text = str(release.get("date") or "")[:10]
        try:
            found.append(date.fromisoformat(text))
        except ValueError:
            continue
    if found and max(found) < since:
        raise RuntimeError("OCDS ha ignorado el filtro de fecha")


def _get(client: httpx.Client, url: str, retries: int = 4) -> dict:
    last = "sin respuesta"
    for attempt in range(retries):
        if attempt:
            time.sleep(5 * attempt)
        try:
            response = client.get(url)
        except httpx.TransportError as exc:
            last = str(exc)
            continue
        if response.status_code == 429 or response.status_code >= 500:
            last = str(response.status_code)
            continue
        if response.status_code >= 400:
            raise RuntimeError(f"OCDS {response.status_code}: {response.text[:300]}")
        return response.json()
    raise RuntimeError(f"OCDS no responde tras {retries} intentos ({last})")


class OcdsSource(Source):
    kind = "api"
    search_url: str = ""
    date_param: str = "updatedFrom"
    notice_base: str = ""

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del vertical
        if not self.search_url:
            raise ValueError("OCDS sin URL de búsqueda")
        url = f"{self.search_url}?{self.date_param}={_stamp(since)}&limit={_PAGE_LIMIT}"
        seen: set[str] = set()
        self.closures: list[str] = []
        with httpx.Client(timeout=40, headers={"User-Agent": "blue-tender/1.0"}) as client:
            for page in range(_MAX_PAGES):
                payload = _get(client, url)
                releases = payload.get("releases") or []
                if page == 0 and releases:
                    _dates_bite(releases, since)
                for release in releases:
                    ocid = str(release.get("ocid") or "")
                    action = release_action(release)
                    if action == "cancel" and ocid:
                        self.closures.append(Opportunity.make_id(self.id, ocid))
                        continue
                    if action != "keep" or not ocid or ocid in seen:
                        continue
                    seen.add(ocid)
                    yield release
                url = str((payload.get("links") or {}).get("next") or "")
                if not url or not releases:
                    return
                time.sleep(3)
        raise RuntimeError(f"OCDS: más de {_MAX_PAGES} páginas; revisa la consulta.")

    def to_tender(self, raw: dict) -> Opportunity:
        tender = raw.get("tender") or {}
        ocid = str(raw.get("ocid") or "")
        title = tender.get("title")
        if not ocid or not title:
            raise ValueError(f"anuncio OCDS de {self.id} sin ocid o sin título")
        period = (tender.get("tenderPeriod") or {}).get("endDate")
        value = tender.get("value") or {}
        amount = value.get("amount")
        currency = value.get("currency")
        budget = None
        if amount is not None and currency:
            budget = Budget(
                amount=float(amount),
                currency=str(currency),
                amount_eur=float(amount) if currency == "EUR" else None,
            )
        buyer_name = (raw.get("buyer") or {}).get("name")
        published = str(raw.get("date") or "")[:10]
        return Opportunity(
            id=Opportunity.make_id(self.id, ocid),
            source_id=self.id,
            external_id=ocid,
            url=f"{self.notice_base}{ocid}",
            type=_notice_type(raw),
            title=str(title),
            description=tender.get("description"),
            buyer=Buyer(name=str(buyer_name), country="GB") if buyer_name else None,
            country="GB",
            language="en",
            budget=budget,
            published_at=date.fromisoformat(published) if published else None,
            deadline_at=_parse_dt(period),
            dedupe_key=ocid,
            raw=raw,
        )
