"""Volcado público de CORDIS (H2020 y Horizon Europe). No es una fuente de convocatorias.

Los zips están en data.europa.eu y se publican en cordis.europa.eu/data (comprobado el
11 nov 2026). Se leen `project.csv`, `topics.csv` y `organization.csv`, separados por
`;`. No se guardan dirección, NIF, geolocalización ni formulario de contacto (ADR 0007).
"""

import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import httpx

from app.keywords import matched_subsectors

# Un volcado que falle no tumba el otro: el job los ejecuta por separado.
SOURCES = {
    "cordis-h2020": {
        "url": "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
        "programme_id": "h2020",
    },
    "cordis-horizon-europe": {
        "url": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
        "programme_id": "horizon-europe",
    },
}

# CORDIS no usa ISO 3166-1 alpha-2 para estos dos. El resto, si no son dos letras, se deja vacío.
_COUNTRY = {"UK": "GB", "EL": "GR"}
_ROLE_RANK = {
    "coordinator": 0,
    "participant": 1,
    "partner": 2,
    "internationalpartner": 2,
    "associatedpartner": 3,
    "thirdparty": 4,
}
_SPLIT = re.compile(r"[;,]")


def country_iso2(code: str | None) -> str | None:
    text = (code or "").strip().upper()
    if not text:
        return None
    text = _COUNTRY.get(text, text)
    if len(text) != 2 or not text.isalpha():
        return None
    return text


def criteria_hash(vertical) -> str:
    """Cambia cuando cambian las keywords con las que se corta el volcado."""
    payload = [
        {"id": sub.id, "keywords": sub.keywords, "project_keywords": sub.project_keywords}
        for sub in vertical.active_subsectors
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def content_hash(parsed: dict) -> str:
    """Hash de las filas ya cortadas. Si no cambia, el job no reescribe."""
    payload = {
        "orgs": _canon(parsed["orgs"], ("id", "pic", "name", "country", "activity_type", "sme")),
        "projects": _canon(
            parsed["projects"],
            (
                "id", "cordis_id", "acronym", "title", "objective", "topics", "topic_title",
                "programme_id", "end_date", "end_year", "subsectors", "url",
            ),
        ),
        "participations": _canon(parsed["participations"], ("org_id", "project_id", "role")),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fetch_zip(url: str, *, etag: str | None = None, modified: str | None = None) -> tuple[bytes | None, dict]:
    """Descarga el zip. `None` significa que el servidor respondió 304: no ha cambiado."""
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified
    with httpx.Client(timeout=600, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
    if response.status_code == 304:
        return None, _headers(response)
    response.raise_for_status()
    return response.content, _headers(response)


def parse_zip(blob: bytes, *, source_id: str, programme_id: str, vertical) -> dict:
    """Corta el volcado con el vertical y descarta bajas, proyectos cancelados y duplicados."""
    archive = zipfile.ZipFile(io.BytesIO(blob))
    projects = _projects(archive, source_id=source_id, programme_id=programme_id, vertical=vertical)
    _attach_topics(archive, projects)
    orgs, participations = _participations(archive, projects)
    return {"orgs": list(orgs.values()), "projects": list(projects.values()), "participations": participations}


def parse_file(path: Path, *, source_id: str, programme_id: str, vertical) -> dict:
    return parse_zip(path.read_bytes(), source_id=source_id, programme_id=programme_id, vertical=vertical)


def _projects(archive: zipfile.ZipFile, *, source_id: str, programme_id: str, vertical) -> dict[str, dict]:
    kept = {}
    subsectors = vertical.active_subsectors
    for row in _csv(archive, "project.csv"):
        if (row.get("status") or "").strip().upper() == "TERMINATED":
            continue
        cordis_id = (row.get("id") or "").strip()
        if not cordis_id:
            continue
        text = " ".join([row.get("title") or "", row.get("objective") or "", row.get("keywords") or ""])
        matched = matched_subsectors(text, subsectors, include_project_keywords=True)
        if not matched:
            continue
        end_date = _date(row.get("endDate"))
        kept[cordis_id] = {
            "id": f"{programme_id}:{cordis_id}",
            "cordis_id": cordis_id,
            "source": source_id,
            "programme_id": programme_id,
            "acronym": (row.get("acronym") or "").strip() or None,
            "title": (row.get("title") or "").strip(),
            "objective": (row.get("objective") or "").strip(),
            "topics": _codes(row.get("topics")),
            "topic_title": "",
            "end_date": end_date,
            "end_year": int(end_date[:4]) if end_date else None,
            "subsectors": matched,
            "url": f"https://cordis.europa.eu/project/id/{cordis_id}",
        }
    return kept


def _attach_topics(archive: zipfile.ZipFile, projects: dict[str, dict]) -> None:
    for row in _csv(archive, "topics.csv"):
        project = projects.get((row.get("projectID") or "").strip())
        if project is None:
            continue
        code = (row.get("topic") or "").strip()
        if code and code not in project["topics"]:
            project["topics"].append(code)
        title = (row.get("title") or "").strip()
        if title and title not in project["topic_title"]:
            project["topic_title"] = f"{project['topic_title']} {title}".strip()


def _participations(archive: zipfile.ZipFile, projects: dict[str, dict]) -> tuple[dict, list[dict]]:
    orgs: dict[str, dict] = {}
    best: dict[tuple[str, str], dict] = {}
    for row in _csv(archive, "organization.csv"):
        cordis_id = (row.get("projectID") or "").strip()
        project = projects.get(cordis_id)
        if project is None:
            continue
        if (row.get("endOfParticipation") or "").strip().lower() == "true":
            continue
        name = (row.get("name") or "").strip()
        if not name:
            continue
        pic = (row.get("organisationID") or "").strip() or None
        org_id = pic or name
        participation = {
            "org_id": org_id,
            "project_id": project["id"],
            "role": (row.get("role") or "").strip() or None,
            "order": _order(row.get("order")),
        }
        key = (org_id, project["id"])
        current = best.get(key)
        if current is None or _prefer(participation, current):
            best[key] = participation
        org = orgs.setdefault(
            org_id,
            {
                "id": org_id,
                "pic": pic,
                "name": name,
                "country": country_iso2(row.get("country")),
                "activity_type": (row.get("activityType") or "").strip() or None,
                "sme": _sme(row.get("SME")),
            },
        )
        if org["country"] is None:
            org["country"] = country_iso2(row.get("country"))
        if org["activity_type"] is None:
            org["activity_type"] = (row.get("activityType") or "").strip() or None
        if org["sme"] is None:
            org["sme"] = _sme(row.get("SME"))
    participations = []
    for row in best.values():
        row.pop("order", None)
        participations.append(row)
    return orgs, participations


def _prefer(new: dict, old: dict) -> bool:
    new_rank = _ROLE_RANK.get((new.get("role") or "").lower(), 9)
    old_rank = _ROLE_RANK.get((old.get("role") or "").lower(), 9)
    if new_rank != old_rank:
        return new_rank < old_rank
    return new["order"] < old["order"]


def _order(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 10**9


def _sme(value) -> bool | None:
    text = (value or "").strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def _date(value: str | None) -> str | None:
    """La fecha que trae la fuente, o vacío. No se inventa un día si solo hay un año."""
    text = (value or "").strip()[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-" and text.replace("-", "").isdigit():
        return text
    return None


def _codes(value: str | None) -> list[str]:
    return [part.strip() for part in _SPLIT.split(value or "") if part.strip()]


def _csv(archive: zipfile.ZipFile, name: str):
    member = next((info for info in archive.namelist() if info.split("/")[-1] == name), None)
    if member is None:
        raise ValueError(f"CORDIS: el zip no trae {name}")
    with archive.open(member) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text, delimiter=";", quotechar='"')


def _headers(response: httpx.Response) -> dict:
    return {key.lower(): value for key, value in response.headers.items()}


def _canon(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    picked = [{key: row.get(key) for key in keys} for row in rows]
    return sorted(picked, key=lambda row: json.dumps(row, sort_keys=True, default=str))
