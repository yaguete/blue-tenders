"""EU Funding & Tenders Portal, Search API pública (clave SEDIA).

Se trae el listado entero de abiertas y próximas. La descripción y el presupuesto
ya vienen en la fila; el detalle solo se pide cuando la descripción falta.
"""

import json
import re
from collections.abc import Iterable
from datetime import date, datetime
from html import unescape

import httpx

from app.models.opportunity import (
    Budget,
    Deadline,
    DeadlineModel,
    Document,
    Fact,
    FactOrigin,
    NoticeKind,
    Opportunity,
    OpportunityKind,
    OpportunityType,
)
from app.sources.base import Source
from app.vertical import Vertical

SEARCH_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
DETAIL_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicDetails/{}.json"
STATUS_FORTHCOMING = "31094501"
STATUS_OPEN = "31094502"
_ACTION = re.compile(r"\b(RIA|IA|CSA)\b")
_TAG = re.compile(r"<[^>]+>")


def _one(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _meta(raw: dict, *keys):
    meta = raw.get("metadata") or {}
    for key in keys:
        if key in meta and meta[key] not in (None, [], ""):
            return _one(meta[key])
    return None


def _all(raw: dict, key: str) -> list:
    value = (raw.get("metadata") or {}).get(key)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("+0000"):
        text = text[:-5] + "+00:00"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _plain(value) -> str | None:
    if not value:
        return None
    text = unescape(_TAG.sub(" ", str(value)))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _action_code(*chunks: str | None) -> str | None:
    for chunk in chunks:
        if not chunk:
            continue
        found = _ACTION.search(chunk)
        if found:
            return found.group(1)
        tail = chunk.split("-")[-1].strip()
        if tail in {"RIA", "IA", "CSA"}:
            return tail
    return None


def _budget_entries(mapping: dict, identifier: str) -> list[dict]:
    """El mapa del portal guarda una lista de acciones por topic, no un objeto."""
    found = []
    for key, entry in mapping.items():
        items = entry if isinstance(entry, list) else [entry]
        for item in items:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action") or "")
            if str(key).startswith(identifier) or action.startswith(identifier):
                found.append(item)
    return found


def _budget_for(raw: dict, identifier: str) -> tuple[float | None, float | None, float | None, int | None]:
    """Presupuesto del topic, mínimo, máximo y proyectos esperados."""
    blob = _meta(raw, "budgetOverview")
    if isinstance(blob, str):
        try:
            blob = json.loads(blob)
        except json.JSONDecodeError:
            blob = None
    if isinstance(blob, dict):
        entries = _budget_entries(blob.get("budgetTopicActionMap") or {}, identifier)
        amounts = []
        grants = []
        for entry in entries:
            for year in entry.get("budgetYearMap") or []:
                if isinstance(year, dict) and year.get("budget") is not None:
                    amounts.append(float(year["budget"]))
            if entry.get("expectedGrants") is not None:
                grants.append(int(entry["expectedGrants"]))
        total = sum(amounts) if amounts else None
        lows = [float(entry["minContribution"]) for entry in entries if entry.get("minContribution") is not None]
        highs = [float(entry["maxContribution"]) for entry in entries if entry.get("maxContribution") is not None]
        return total, min(lows) if lows else None, max(highs) if highs else None, grants[0] if grants else None
    raw_amount = _meta(raw, "budget", "callBudget")
    try:
        amount = float(str(raw_amount).replace(",", "")) if raw_amount is not None else None
    except ValueError:
        amount = None
    return amount, None, None, None


def _deadlines(raw: dict, today: date) -> tuple[datetime | None, DeadlineModel, list[Deadline], bool]:
    parsed = [item for item in (_parse_dt(value) for value in _all(raw, "deadlineDate")) if item]
    if not parsed:
        actions = _meta(raw, "actions")
        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except json.JSONDecodeError:
                actions = None
        if isinstance(actions, list):
            for action in actions:
                for stamp in action.get("deadlineDates") or []:
                    found = _parse_dt(stamp)
                    if found:
                        parsed.append(found)
    parsed.sort()
    if not parsed:
        return None, DeadlineModel.single, [], False
    forthcoming = str(_meta(raw, "status") or "") == STATUS_FORTHCOMING
    timeless = forthcoming and all(item.hour == 0 and item.minute == 0 and item.second == 0 for item in parsed)
    rows = [Deadline(phase="deadline", at=item, timezone="Europe/Brussels") for item in parsed]
    if len(parsed) == 1:
        return parsed[0], DeadlineModel.single, rows, timeless
    if len(parsed) == 2:
        return parsed[0], DeadlineModel.two_stage, rows, timeless
    upcoming = [item for item in parsed if item.date() >= today]
    chosen = upcoming[0] if upcoming else parsed[-1]
    return chosen, DeadlineModel.multiple_cutoff, rows, timeless


def _reference(raw: dict) -> str:
    return str(_meta(raw, "reference") or _meta(raw, "identifier") or "")


_HEADING = re.compile(r"(?is)<h[1-4][^>]*>(.*?)</h[1-4]>")
_PORTAL_KIND = re.compile(
    r'(?is)<p[^>]*class="[^"]*topicdescriptionkind[^"]*"[^>]*>(.*?)</p>'
)
_PDF_URL = re.compile(r"https?://[^\"\\\s>]+\.pdf", re.IGNORECASE)
_ANNEX = re.compile(r"general[-_\s]?annex", re.IGNORECASE)


def is_general_annex(url: str) -> bool:
    """Los anexos generales del programa son un PDF compartido, no un documento del topic."""
    return _ANNEX.search(url) is not None


def portal_pdfs(raw: dict) -> list[str]:
    found = []
    for url in _PDF_URL.findall(json.dumps(raw)):
        if url not in found:
            found.append(url)
    return found


def topic_text_from_detail(payload: dict) -> str | None:
    """Texto del topic a partir del JSON `topicDetails`, no de la página del portal."""
    detail = payload.get("TopicDetails") if isinstance(payload, dict) else None
    if not isinstance(detail, dict):
        detail = payload if isinstance(payload, dict) else {}
    parts = []
    for key, heading in (("description", None), ("conditions", "Conditions")):
        html = detail.get(key)
        if not html or not isinstance(html, str):
            continue
        text = _description({"metadata": {key: [html]}}) if key == "description" else None
        if key == "conditions":
            text = _sections_html(html)
            if text:
                text = f"## {heading}\n\n{text}" if not text.startswith("## ") else text
        if text:
            parts.append(text)
    return "\n\n".join(parts) or None


def load_topic_text(identifier: str) -> str | None:
    """Descarga el detalle público del topic. La página HTML del portal no trae el texto."""
    if not identifier:
        return None
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            response = client.get(DETAIL_URL.format(identifier.lower()))
            response.raise_for_status()
            return topic_text_from_detail(response.json())
    except (httpx.HTTPError, ValueError):
        return None


def _sections_html(html: str) -> str | None:
    marked = _PORTAL_KIND.sub(r"<h2>\1</h2>", html)
    headings = list(_HEADING.finditer(marked))
    if not headings:
        return _plain(marked)
    chunks = []
    preamble = _plain(marked[: headings[0].start()])
    if preamble:
        chunks.append(f"## Overview\n\n{preamble}")
    for index, match in enumerate(headings):
        title = _plain(match.group(1)) or "Section"
        next_start = headings[index + 1].start() if index + 1 < len(headings) else len(marked)
        body = _plain(marked[match.end() : next_start])
        if body:
            chunks.append(f"## {title}\n\n{body}")
    return "\n\n".join(chunks) or _plain(marked)


def _description(raw: dict) -> str | None:
    """Texto del topic. Si el HTML trae títulos, se conservan como secciones (`##`)."""
    value = _meta(raw, "descriptionByte", "description", "summary")
    if not value:
        return None
    return _sections_html(str(value))


class EuFtSource(Source):
    id = "eu-ft"
    kind = "api"
    statuses = (STATUS_FORTHCOMING, STATUS_OPEN)

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del since, vertical
        query = {
            "bool": {
                "must": [
                    {"terms": {"type": ["1", "2", "8"]}},
                    {"terms": {"status": list(self.statuses)}},
                ]
            }
        }
        kept: dict[str, dict] = {}
        page = 1
        with httpx.Client(timeout=40) as client:
            while page <= 30:
                response = client.post(
                    SEARCH_URL,
                    params={"apiKey": "SEDIA", "text": "***", "pageSize": "100", "pageNumber": str(page)},
                    files={
                        "query": ("blob", json.dumps(query), "application/json"),
                        "languages": ("blob", json.dumps(["en"]), "application/json"),
                        "sort": (
                            "blob",
                            json.dumps({"field": "sortStatus", "order": "ASC"}),
                            "application/json",
                        ),
                    },
                )
                response.raise_for_status()
                results = response.json().get("results") or []
                if not results:
                    break
                for row in results:
                    key = _reference(row)
                    if not key:
                        continue
                    previous = kept.get(key)
                    if previous is None or (not _description(previous) and _description(row)):
                        kept[key] = row
                if len(results) < 100:
                    break
                page += 1
            for row in kept.values():
                if not _description(row):
                    _fill_detail(client, row)
                yield row

    def to_tender(self, raw: dict) -> Opportunity:
        type_code = str(_one((raw.get("metadata") or {}).get("type")) or "1")
        identifier = str(_meta(raw, "identifier") or "")
        cascade_id = str(_meta(raw, "callccm2Id") or _meta(raw, "reference") or "")
        if type_code == "8":
            external = f"cascade-{cascade_id or identifier}"
            title = _meta(raw, "callTitle") or _meta(raw, "title")
        else:
            external = identifier or str(_meta(raw, "reference") or "")
            title = _meta(raw, "title") or _meta(raw, "callTitle")
        if not external or not title:
            raise ValueError("tema del portal sin identificador o sin título")
        deadline, model, deadlines, timeless = _deadlines(raw, date.today())
        opening = _parse_dt(_meta(raw, "startDate"))
        action = _action_code(
            str(_meta(raw, "typesOfAction", "typeOfAction") or ""),
            json.dumps(_meta(raw, "actions") or ""),
        )
        programme = _meta(raw, "frameworkProgramme", "programmePeriod")
        kind = OpportunityKind.grant
        notice = NoticeKind.cascade if type_code == "8" else NoticeKind.call_for_proposals
        total, low, high, grants = _budget_for(raw, identifier or external)
        url = _public_url(raw, identifier, type_code)
        description = _description(raw)
        if type_code == "8":
            description = _plain(_meta(raw, "description")) or description
        facts = []
        if grants is not None:
            facts.append(Fact(field="expected_grants", value=grants, origin=FactOrigin.source, confidence=0.9))
        if timeless:
            facts.append(Fact(field="deadline_time", value="unknown", origin=FactOrigin.source, confidence=0.9))
        latest = _meta(raw, "latestInfos")
        if latest:
            facts.append(Fact(field="latest_info", value=str(latest)[:500], origin=FactOrigin.source, confidence=0.8))
        documents = _call_documents(raw, str(url))
        if _meta(raw, "allowPartnerSearch") in (True, "true", "True"):
            documents.append(
                Document(
                    url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/partner-search/"
                    + (identifier or external),
                    name="Partner search",
                    kind="html",
                    access="link_only",
                )
            )
        return Opportunity(
            id=Opportunity.make_id(self.id, external),
            source_id=self.id,
            external_id=external,
            url=str(url),
            type=OpportunityType.grant,
            kind=kind,
            notice=notice,
            title=str(title),
            title_en=str(title),
            description=description,
            language="en",
            programme_id=_programme(programme, identifier or external),
            topic_id=identifier or None,
            type_of_action=action,
            mission_ocean=identifier.startswith("HORIZON-MISS") and "OCEAN" in identifier,
            budget=Budget(amount=total, currency="EUR", amount_eur=total) if total else None,
            budget_total_eur=total,
            amount_min_eur=low,
            amount_max_eur=high,
            opens_at=opening,
            deadline_at=deadline,
            deadline_model=model,
            deadlines=deadlines,
            documents=documents,
            facts=facts,
            raw=raw,
        )


def _call_documents(raw: dict, url: str) -> list[Document]:
    """El documento del topic es su texto. Los anexos generales no se copian en cada ficha."""
    if _description(raw):
        documents = [
            Document(url=f"{url}#topic-text", name="Topic text", kind="topic_text", access="inline")
        ]
    else:
        documents = [Document(url=url, name="Topic page", kind="html", access="fetch")]
    return documents


def _public_url(raw: dict, identifier: str, type_code: str) -> str:
    url = str(raw.get("url") or "")
    if url and not url.endswith(".json") and "topicDetails" not in url.split("/")[-1]:
        return url
    if type_code == "8" or url.endswith(".json"):
        parent = identifier or str(_meta(raw, "identifier") or "")
        if parent:
            return (
                "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
                + parent.lower()
            )
    if identifier:
        return (
            "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
            + identifier
        )
    return url or "https://ec.europa.eu/info/funding-tenders/opportunities/portal/"


def _fill_detail(client: httpx.Client, row: dict) -> None:
    identifier = str(_meta(row, "identifier") or "")
    if not identifier:
        return
    try:
        response = client.get(DETAIL_URL.format(identifier.lower()), timeout=20)
        if response.status_code != 200:
            return
        detail = response.json()
    except (httpx.HTTPError, ValueError):
        return
    meta = row.setdefault("metadata", {})
    for key in ("descriptionByte", "budgetOverview", "topicConditions"):
        if not meta.get(key) and detail.get(key):
            meta[key] = detail[key]


def _programme(label, identifier: str) -> str | None:
    text = f"{label or ''} {identifier}".lower()
    if "horizon" in text or identifier.startswith("HORIZON"):
        return "horizon-europe"
    if "life" in text:
        return "life"
    if "cef" in text:
        return "cef-energy"
    if identifier.startswith("EMFAF"):
        return "emfaf"
    if "innov" in text:
        return "innovation-fund"
    return None
