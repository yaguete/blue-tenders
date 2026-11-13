"""EU Funding & Tenders Portal, Search API pública (clave SEDIA).

Se trae el listado entero de abiertas y próximas. El detalle (`TopicDetails`) se pide
si faltan la descripción, el presupuesto o la call: ahí están el texto, las condiciones
y `budgetOverviewJSONItem`.
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


def _budget_blob(raw: dict) -> dict | None:
    blob = _meta(raw, "budgetOverview")
    if isinstance(blob, str):
        try:
            blob = json.loads(blob)
        except json.JSONDecodeError:
            return None
    return blob if isinstance(blob, dict) else None


def _action_topic(action: str) -> str:
    """El portal escribe `HORIZON-CL5-2023-D3-02-10 - HORIZON-RIA ...`. El código es lo de antes."""
    if " - " not in action:
        return ""
    return action.split(" - ", 1)[0].strip()


def _budget_entries(mapping: dict, identifier: str) -> list[dict]:
    """Una entrada casa si su código de topic es exactamente el identificador.

    La clave del mapa a veces es el identificador (el fixture) y a veces un id numérico
    del portal. `startswith` hacía que `-1` se quedara con el presupuesto de `-10`.
    """
    found = []
    for key, entry in mapping.items():
        items = entry if isinstance(entry, list) else [entry]
        for item in items:
            if not isinstance(item, dict):
                continue
            code = _action_topic(str(item.get("action") or ""))
            if code == identifier or str(key) == identifier:
                found.append(item)
    return found


def _year_amounts(entry: dict) -> list[float]:
    years = entry.get("budgetYearMap") or []
    amounts = []
    if isinstance(years, dict):
        for value in years.values():
            if value is not None:
                amounts.append(float(value))
        return amounts
    if isinstance(years, list):
        for year in years:
            if isinstance(year, dict) and year.get("budget") is not None:
                amounts.append(float(year["budget"]))
    return amounts


def _topic_codes(blob: dict) -> set[str]:
    mapping = blob.get("budgetTopicActionMap") or {}
    if not isinstance(mapping, dict):
        return set()
    codes: set[str] = set()
    for key, entry in mapping.items():
        items = entry if isinstance(entry, list) else [entry]
        named = False
        for item in items:
            if not isinstance(item, dict):
                continue
            code = _action_topic(str(item.get("action") or ""))
            if code:
                codes.add(code)
                named = True
        key_text = str(key)
        if not named and "-" in key_text and any(char.isdigit() for char in key_text):
            codes.add(key_text)
    return codes


def _budget_for(raw: dict, identifier: str) -> tuple[float | None, float | None, float | None, int | None]:
    """Presupuesto del topic, mínimo, máximo y proyectos esperados."""
    blob = _budget_blob(raw)
    if isinstance(blob, dict):
        entries = _budget_entries(blob.get("budgetTopicActionMap") or {}, identifier)
        amounts = []
        grants = []
        for entry in entries:
            amounts.extend(_year_amounts(entry))
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


def _latest_contents(raw: dict) -> list[str]:
    value = (raw.get("metadata") or {}).get("latestInfos")
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    contents = []
    for item in items:
        if isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                contents.append(content)
        elif isinstance(item, str) and item.strip():
            contents.append(item)
    return contents


def _info_lines(raw: dict) -> list[str]:
    lines = []
    for content in _latest_contents(raw):
        for part in re.split(r"</p>|<br\s*/?>", content, flags=re.IGNORECASE):
            line = _plain(unescape(part))
            if line:
                lines.append(line)
    return lines


def _proposals_submitted(raw: dict, identifier: str) -> tuple[int, str] | None:
    """La línea del portal que dice cuántas propuestas llegaron a este topic, o nada.

    `-1` no puede casar con `-10`. Si dos líneas dan números distintos, no se guarda.
    """
    if not identifier:
        return None
    pattern = re.compile(rf"{re.escape(identifier)}(?!\d).*?(\d+)\s+proposals?\b", re.IGNORECASE)
    hits: list[tuple[int, str]] = []
    for line in _info_lines(raw):
        match = pattern.search(line)
        if match:
            hits.append((int(match.group(1)), line))
    numbers = {count for count, _line in hits}
    if len(numbers) != 1:
        return None
    return hits[0]


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
                if (
                    not _description(row)
                    or not _meta(row, "callIdentifier")
                    or not _budget_blob(row)
                ):
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
        conditions = _meta(raw, "topicConditions")
        if conditions:
            extra = _sections_html(str(conditions))
            if extra:
                if not extra.startswith("## "):
                    extra = f"## Conditions\n\n{extra}"
                description = f"{description}\n\n{extra}" if description else extra
        facts = []
        if grants is not None:
            facts.append(Fact(field="expected_grants", value=grants, origin=FactOrigin.source, confidence=0.9))
        call_title = _meta(raw, "callTitle")
        if call_title and str(call_title) != str(title):
            facts.append(Fact(field="call_title", value=str(call_title), origin=FactOrigin.source, confidence=0.9))
        blob = _budget_blob(raw)
        if blob:
            count = len(_topic_codes(blob))
            if count:
                facts.append(
                    Fact(field="call_topics_count", value=count, origin=FactOrigin.source, confidence=0.9)
                )
        submitted = _proposals_submitted(raw, identifier)
        if submitted:
            count, line = submitted
            facts.append(
                Fact(
                    field="proposals_submitted",
                    value=count,
                    origin=FactOrigin.source,
                    confidence=0.8,
                    quote=line[:500],
                )
            )
        if timeless:
            facts.append(Fact(field="deadline_time", value="unknown", origin=FactOrigin.source, confidence=0.9))
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
            call_id=str(_meta(raw, "callIdentifier") or "") or None,
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


def _topic_details(payload: dict) -> dict:
    inner = payload.get("TopicDetails") if isinstance(payload, dict) else None
    if isinstance(inner, dict):
        return inner
    return payload if isinstance(payload, dict) else {}


def _fill_detail(client: httpx.Client, row: dict) -> None:
    identifier = str(_meta(row, "identifier") or "")
    if not identifier:
        return
    try:
        response = client.get(DETAIL_URL.format(identifier.lower()), timeout=20)
        if response.status_code != 200:
            return
        detail = _topic_details(response.json())
    except (httpx.HTTPError, ValueError):
        return
    meta = row.setdefault("metadata", {})
    copies = {
        "descriptionByte": detail.get("description"),
        "topicConditions": detail.get("conditions"),
        "budgetOverview": detail.get("budgetOverviewJSONItem") or detail.get("budgetOverview"),
        "callIdentifier": detail.get("callIdentifier"),
        "callTitle": detail.get("callTitle"),
        "latestInfos": detail.get("latestInfos"),
    }
    for key, value in copies.items():
        if value and not meta.get(key):
            meta[key] = value


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
