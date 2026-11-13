"""Herramientas del modo general. Solo lectura, sin web.

`search_opportunities` no devuelve adjudicaciones: su ficha da 404.
"""

import json
from datetime import date, datetime

from app.catalog import funder_profiles, read_yaml_list
from app.models.opportunity import Opportunity
from app.search.query import SearchFilters, search_opportunities
from app.settings import settings

MAX_ROUNDS = 4


def tool_specs(include_documents: bool) -> list[dict]:
    specs = [
        {
            "name": "search_opportunities",
            "description": "Search open calls in the index. Award notices are excluded.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "before": {"type": "string", "description": "YYYY-MM-DD. Only calls whose deadline is before this day."},
                },
            },
        },
        {
            "name": "get_opportunity",
            "description": "Read one call by id. Returns nothing for award notices.",
            "input_schema": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
        {
            "name": "search_knowledge",
            "description": "Look up a term in the project glossary.",
            "input_schema": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        },
        {
            "name": "list_funders",
            "description": "List funders in the directory. They are not calls.",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    ]
    if include_documents:
        specs.append(
            {
                "name": "search_documents",
                "description": "Find pages in call documents that did not fit in the prompt.",
                "input_schema": {
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                    "required": ["q"],
                },
            }
        )
    return specs


def search_calls(items: list[Opportunity], question: str, before: str | None = None) -> list[dict]:
    filters = SearchFilters(q=question or None, limit=8)
    found = search_opportunities([item for item in items if item.searchable()], filters)
    day = _day(before)
    rows = []
    for item in found["items"]:
        if day and item.deadline_at and item.deadline_at.date() >= day:
            continue
        rows.append(
            {
                "id": item.id,
                "title": item.title_en or item.title,
                "deadline_at": item.deadline_at.isoformat() if item.deadline_at else None,
                "url": item.url,
                "status": item.status.value if item.status else None,
            }
        )
    return rows


def opportunity_brief(item: Opportunity | None) -> dict:
    if item is None or not item.searchable():
        return {"error": "not a call in the index"}
    return {
        "id": item.id,
        "title": item.title_en or item.title,
        "summary": item.summary_en or item.description,
        "deadline_at": item.deadline_at.isoformat() if item.deadline_at else None,
        "url": item.url,
    }


def knowledge(question: str) -> list[dict]:
    entries = read_yaml_list(settings.config_dir / "knowledge" / "glossary.yaml")
    words = {part.lower() for part in question.split() if len(part) >= 3}
    hits = []
    for entry in entries:
        blob = " ".join(
            [entry.get("title") or "", " ".join(entry.get("keywords") or [])]
        ).lower()
        if any(word in blob for word in words):
            hits.append({"id": entry.get("id"), "title": entry.get("title"), "text": entry.get("text")})
    return hits[:3]


def funders(question: str) -> list[dict]:
    words = {part.lower() for part in (question or "").split() if len(part) >= 3}
    rows = []
    for funder in funder_profiles():
        blob = f"{funder.name} {funder.summary}".lower()
        if words and not any(word in blob for word in words):
            continue
        rows.append({"id": funder.id, "name": funder.name, "url": funder.url, "summary": funder.summary})
    return rows[:8]


def search_pages(documents: list[dict], question: str) -> list[dict]:
    from app.assistant.engine import rank_pages

    pages = []
    for doc in documents:
        for page in doc.get("pages") or []:
            pages.append({**page, "name": doc.get("name"), "url": doc.get("document_url")})
    return [
        {
            "name": page.get("name"),
            "url": page.get("url"),
            "page": page.get("page"),
            "heading": page.get("heading"),
            "text": (page.get("text") or "")[:500],
        }
        for page in rank_pages(pages, question)[:5]
    ]


def run_tool(name: str, payload: dict, items: list[Opportunity], documents: list[dict]) -> dict:
    if name == "search_opportunities":
        return {"calls": search_calls(items, payload.get("q") or "", payload.get("before"))}
    if name == "get_opportunity":
        item = next((candidate for candidate in items if candidate.id == payload.get("id")), None)
        return opportunity_brief(item)
    if name == "search_knowledge":
        return {"entries": knowledge(payload.get("q") or "")}
    if name == "list_funders":
        return {"funders": funders(payload.get("q") or "")}
    if name == "search_documents":
        return {"pages": search_pages(documents, payload.get("q") or "")}
    return {"error": "unknown tool"}


def dump(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)[:8000]


def _day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None
