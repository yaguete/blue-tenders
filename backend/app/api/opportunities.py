"""Búsqueda y ficha. Público, sin cuenta."""

import time
from datetime import UTC, date, datetime
from html import unescape
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.matching.fit import explain_fit
from app.models.opportunity import Opportunity, compute_status
from app.partners.track_record import track_record_for
from app.quality.text import plain_text
from app.search.query import SearchFilters, match_reason, search_opportunities, suggest_relaxation
from app.search.stats import platform_stats
from app.vertical import load_vertical

_CACHE: dict = {"at": 0.0, "items": None}
_STATS_CACHE: dict = {"at": 0.0, "body": None}


def cached_opportunities():
    now = time.monotonic()
    if _CACHE["items"] is not None and now - _CACHE["at"] < 300:
        return _CACHE["items"]
    items = get_store().opportunities()
    _CACHE["at"] = now
    _CACHE["items"] = items
    return items


def cached_stats() -> dict:
    """La frescura pagina `ingest_runs` entera. No hace falta repetirlo en cada visita."""
    now = time.monotonic()
    if _STATS_CACHE["body"] is not None and now - _STATS_CACHE["at"] < 300:
        return _STATS_CACHE["body"]
    body = platform_stats(cached_opportunities(), get_store().source_freshness())
    _STATS_CACHE["at"] = now
    _STATS_CACHE["body"] = body
    return body


from app.store import get_store

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _filters(
    q: str | None,
    kind: list[str],
    status: list[str],
    subsector: list[str],
    programme_id: list[str],
    country: list[str],
    entity_type: str | None,
    consortium_required: bool | None,
    mission_ocean: bool | None,
    amount_min: float | None,
    amount_max: float | None,
    cofunding_min: float | None,
    sea_basin: list[str],
    trl: int | None,
    closing_within_days: int | None,
    deadline: list[str],
    exclude_unknown: bool,
    limit: int,
    offset: int,
) -> SearchFilters:
    return SearchFilters(
        q=q,
        kind=kind,
        status=status,
        subsector=subsector,
        programme_id=programme_id,
        country=country or [],
        entity_type=entity_type,
        consortium_required=consortium_required,
        mission_ocean=mission_ocean,
        amount_min=amount_min,
        amount_max=amount_max,
        cofunding_min=cofunding_min,
        sea_basin=sea_basin,
        trl=trl,
        closing_within_days=closing_within_days,
        deadline=deadline,
        exclude_unknown=exclude_unknown,
        limit=limit,
        offset=offset,
    )


@router.get("")
def search(
    q: str | None = None,
    kind: Annotated[list[str] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
    subsector: Annotated[list[str] | None, Query()] = None,
    programme_id: Annotated[list[str] | None, Query()] = None,
    country: Annotated[list[str] | None, Query()] = None,
    entity_type: str | None = None,
    consortium_required: bool | None = None,
    mission_ocean: bool | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    cofunding_min: float | None = None,
    sea_basin: Annotated[list[str] | None, Query()] = None,
    trl: int | None = None,
    closing_within_days: int | None = None,
    deadline: Annotated[list[str] | None, Query()] = None,
    exclude_unknown: bool = False,
    limit: Annotated[int, Query(le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    profile_subsector: Annotated[list[str] | None, Query()] = None,
    profile_country: str | None = None,
    profile_entity: str | None = None,
    profile_trl: int | None = None,
) -> dict:
    items = cached_opportunities()
    filters = _filters(
        q, kind or [], status or [], subsector or [], programme_id or [], country or [], entity_type,
        consortium_required, mission_ocean, amount_min, amount_max, cofunding_min, sea_basin or [],
        trl, closing_within_days, deadline or [], exclude_unknown, limit, offset,
    )
    found = search_opportunities(items, filters)
    profile = None
    if profile_country or profile_entity or profile_subsector or profile_trl:
        profile = {
            "country": profile_country,
            "entity_type": profile_entity,
            "subsectors": profile_subsector or [],
            "trl": profile_trl,
        }
    rows = []
    for item in found["items"]:
        row = _card(item)
        if q:
            row["why"] = match_reason(item, q)
        fit = explain_fit(item, profile)
        if fit:
            row["fit"] = fit
        rows.append(row)
    if profile:
        # Solo reordena esta página. Con offset, las páginas no encajan entre sí.
        # /search no manda profile_*.
        rows.sort(key=lambda row: {"strong": 0, "possible": 1, "check": 2, "likely_ineligible": 3}.get(
            (row.get("fit") or {}).get("level"), 2
        ))
        hidden = sum(1 for row in rows if (row.get("fit") or {}).get("level") == "likely_ineligible")
    else:
        hidden = 0
    suggestion = suggest_relaxation(items, filters) if found["total"] == 0 else None
    return {
        "total": found["total"],
        "counts": found["counts"],
        "unknown": found["unknown"],
        "facets": found["facets"],
        "hidden_ineligible": hidden,
        "suggestion": suggestion,
        "items": [row for row in rows if (row.get("fit") or {}).get("level") != "likely_ineligible"],
    }


@router.get("/stats")
def stats() -> dict:
    return cached_stats()


@router.get("/{opportunity_id}")
def detail(opportunity_id: str) -> dict:
    store = get_store()
    item = store.get(opportunity_id)
    if item is None or not item.searchable():
        raise HTTPException(status_code=404, detail="Opportunity not found")
    payload = item.model_dump(mode="json")
    for field in ("title", "title_en", "description"):
        payload[field] = unescape(payload[field]) if payload.get(field) else payload.get(field)
    payload["summary_en"] = plain_text(payload.get("summary_en")) or None
    analysis = payload.get("analysis")
    if analysis:
        analysis["summary"] = plain_text(analysis.get("summary")) or None
        for block in analysis.get("blocks") or []:
            block["heading"] = plain_text(block.get("heading"))
            block["text"] = plain_text(block.get("text"))
    payload["status"] = compute_status(item).value
    record = track_record_for(item, store, load_vertical())
    payload["track_record"] = record
    payload["partners"] = record["items"]
    payload["awards"] = store.awards_for(item.call_id)
    payload["updated_at"] = item.analysis.updated_at.isoformat() if item.analysis and item.analysis.updated_at else None
    return payload


@router.get("/{opportunity_id}/calendar", response_class=PlainTextResponse)
def calendar(opportunity_id: str) -> str:
    item = get_store().get(opportunity_id)
    if item is None or item.deadline_at is None:
        raise HTTPException(status_code=404, detail="No deadline to export")
    return _ics(item)


def _card(item: Opportunity) -> dict:
    return {
        "id": item.id,
        "title": unescape(item.title) if item.title else item.title,
        "title_en": unescape(item.title_en) if item.title_en else item.title_en,
        "summary_en": plain_text(item.summary_en) or None,
        "kind": item.kind.value if item.kind else None,
        "status": item.status.value if item.status else None,
        "programme_id": item.programme_id,
        "funder_id": item.funder_id,
        "country": item.country,
        "deadline_at": item.deadline_at.isoformat() if item.deadline_at else None,
        "budget_total_eur": item.budget_total_eur,
        "budget_amount": item.budget.amount if item.budget else None,
        "budget_currency": item.budget.currency if item.budget else None,
        "amount_min_eur": item.amount_min_eur,
        "amount_max_eur": item.amount_max_eur,
        "cofunding_min": item.cofunding_min,
        "cofunding_max": item.cofunding_max,
        "subsectors": item.subsectors,
        "relevance": item.relevance,
        "url": item.url,
        "language": item.language,
    }


def _ics(item: Opportunity) -> str:
    when = item.deadline_at
    assert when is not None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    stamp = when.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    title = (item.title_en or item.title).replace("\n", " ")
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//blue-tender//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{item.id}@blue-tender\r\n"
        f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}\r\n"
        f"DTSTART:{stamp}\r\n"
        f"SUMMARY:{title}\r\n"
        f"URL:{item.url}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@router.post("/{opportunity_id}/report")
def report(opportunity_id: str, body: dict) -> dict:
    store = get_store()
    item = store.get(opportunity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    data = store.load()
    entry = {
        "opportunity_id": opportunity_id,
        "field": body.get("field"),
        "note": (body.get("note") or "")[:500],
        "at": date.today().isoformat(),
    }
    data["reports"].append(entry)
    data["reviews"].append({**entry, "reason": "user_report", "resolved": False})
    store.save(data)
    return {"ok": True}
