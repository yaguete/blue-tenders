"""BDNS: convocatorias de subvenciones y préstamos en España.

La búsqueda se hace por descripción, en español, y el plazo y el importe salen
del detalle. No se bajan concesiones. Un plazo que venga como frase ("un mes
desde la publicación") no se convierte en fecha. La hora solo se guarda si
`textFin` la dice.
"""

import re
from collections.abc import Iterable
from datetime import date, datetime

import httpx

from app.models.opportunity import (
    Budget,
    Buyer,
    Document,
    Fact,
    FactOrigin,
    NoticeKind,
    Opportunity,
    OpportunityKind,
    OpportunityType,
)
from app.sources.base import SOURCE_SUBSECTORS, Source
from app.sources.terms import search_pairs
from app.vertical import Vertical

SEARCH_URL = "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/busqueda"
DETAIL_URL = "https://www.infosubvenciones.es/bdnstrans/api/convocatorias"
_TIME = re.compile(r"(\d{1,2}):(\d{2})")

_INSTRUMENT = {
    "subvención": OpportunityKind.grant,
    "subvencion": OpportunityKind.grant,
    "préstamo": OpportunityKind.loan,
    "prestamo": OpportunityKind.loan,
    "aval": OpportunityKind.loan,
}


def _parse_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text, fmt).date()
        except ValueError:
            continue
    return None


def filters_bite(filtered_total: int, unfiltered_total: int) -> None:
    """BDNS ignora un parámetro desconocido y devuelve el archivo entero, con un 200."""
    if filtered_total >= unfiltered_total:
        raise RuntimeError("BDNS ha ignorado el filtro: el total no baja")


class BdnsSource(Source):
    id = "bdns"
    kind = "api"
    # Busca por término: un día sin resultados no es un fallo de la fuente.
    volume_alert = False

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        pairs = search_pairs(vertical, self.id)
        if not pairs:
            raise ValueError("BDNS: el vertical no tiene search_terms.bdns; no se baja el archivo entero.")
        seen: dict[str, dict] = {}
        checked = False
        with httpx.Client(timeout=40, headers={"Accept": "application/json"}) as client:
            for subsector, keyword in pairs:
                page = 0
                while page < 20:
                    params = {
                        "descripcion": keyword,
                        "fechaDesde": since.strftime("%d/%m/%Y"),
                        "page": page,
                        "pageSize": 50,
                    }
                    response = client.get(SEARCH_URL, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    if not checked:
                        bare = client.get(
                            SEARCH_URL,
                            params={"fechaDesde": since.strftime("%d/%m/%Y"), "page": 0, "pageSize": 1},
                        )
                        bare.raise_for_status()
                        left = payload.get("totalElements")
                        right = bare.json().get("totalElements")
                        if left is not None and right is not None:
                            filters_bite(int(left), int(right))
                        checked = True
                    rows = payload.get("content") or payload.get("convocatorias") or []
                    if not rows:
                        break
                    for row in rows:
                        number = str(row.get("numeroConvocatoria") or row.get("codigoBDNS") or "")
                        if not number:
                            continue
                        if number in seen:
                            _remember(seen[number], subsector)
                            continue
                        detailed = _with_detail(client, row, number)
                        _remember(detailed, subsector)
                        seen[number] = detailed
                    if len(rows) < 50:
                        break
                    page += 1
        yield from seen.values()

    def to_tender(self, raw: dict) -> Opportunity:
        external = str(raw.get("codigoBDNS") or raw.get("numeroConvocatoria") or "")
        title = raw.get("titulo") or raw.get("descripcion")
        if not external or not title:
            raise ValueError("convocatoria BDNS sin código o sin título")
        instruments = " ".join(raw.get("instrumentos") or []).lower()
        if isinstance(raw.get("instrumentos"), list):
            instruments = " ".join(str(x) for x in raw["instrumentos"]).lower()
        kind = OpportunityKind.grant
        for needle, mapped in _INSTRUMENT.items():
            if needle in instruments:
                kind = mapped
                break
        published = _parse_date(raw.get("fechaPublicacion") or raw.get("fechaRecepcion"))
        # Solo fechas de calendario. El texto libre se conserva en la descripción.
        deadline = _deadline(raw)
        amount = raw.get("presupuestoTotal") or raw.get("importeTotal")
        try:
            amount_f = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            amount_f = None
        entities = raw.get("tiposBeneficiarios") or []
        if isinstance(entities, str):
            entities = [entities]
        organ = raw.get("organo")
        return Opportunity(
            id=Opportunity.make_id(self.id, external),
            source_id=self.id,
            external_id=external,
            url=raw.get("convocatoriaBases")
            or f"https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/{external}",
            type=OpportunityType.grant if kind == OpportunityKind.grant else OpportunityType.tender,
            kind=kind,
            notice=NoticeKind.call_for_proposals,
            title=str(title),
            description=raw.get("descripcion") or raw.get("descripcionFinalidad"),
            buyer=Buyer(name=str(organ), country="ES") if organ else None,
            country="ES",
            language="es",
            published_at=published,
            deadline_at=deadline,
            budget=Budget(amount=amount_f, currency="EUR", amount_eur=amount_f) if amount_f else None,
            budget_total_eur=amount_f,
            eligible_entity_types=[str(item) for item in entities],
            documents=_documents(raw),
            facts=_facts(raw),
            raw=raw,
        )


def _deadline(raw: dict) -> datetime | None:
    day = _parse_date(raw.get("fechaFinSolicitud") or raw.get("fechaFin") or raw.get("fechaCierre"))
    if day is None:
        return None
    found = _TIME.search(str(raw.get("textFin") or ""))
    if not found:
        return datetime(day.year, day.month, day.day)
    return datetime(day.year, day.month, day.day, int(found.group(1)), int(found.group(2)))


def _documents(raw: dict) -> list[Document]:
    """PDF de la convocatoria y bases reguladoras, si el detalle los trae."""
    documents = []
    seen = set()
    rows = raw.get("documentos") or []
    if isinstance(rows, dict):
        rows = [rows]
    for item in rows:
        if isinstance(item, str):
            url, name = item, "Call (PDF)"
        elif isinstance(item, dict):
            url = item.get("url") or item.get("enlace") or item.get("urlDocumento")
            name = item.get("nombre") or item.get("descripcion") or "Call (PDF)"
        else:
            continue
        if not url or url in seen:
            continue
        seen.add(url)
        documents.append(Document(url=str(url), name=str(name), kind="notice", access="fetch"))
    bases = raw.get("urlBasesReguladoras")
    if bases and bases not in seen:
        documents.append(Document(url=str(bases), name="Regulatory bases", kind="bases", access="fetch"))
    return documents


def _facts(raw: dict) -> list[Fact]:
    facts = []
    if raw.get("fondos"):
        facts.append(Fact(field="fund", value=raw.get("fondos"), origin=FactOrigin.source, confidence=0.9))
    if raw.get("textFin") and not _TIME.search(str(raw.get("textFin"))):
        facts.append(
            Fact(field="deadline_time", value="unknown", origin=FactOrigin.source, confidence=0.6, quote=str(raw.get("textFin"))[:240])
        )
    return facts


def _remember(row: dict, subsector: str) -> None:
    found = row.setdefault(SOURCE_SUBSECTORS, [])
    if subsector not in found:
        found.append(subsector)


def _with_detail(client: httpx.Client, row: dict, number: str) -> dict:
    try:
        response = client.get(DETAIL_URL, params={"numConv": number})
        response.raise_for_status()
        detail = response.json()
    except (httpx.HTTPError, ValueError):
        return row
    if isinstance(detail, list):
        detail = detail[0] if detail else {}
    if isinstance(detail, dict):
        merged = dict(row)
        merged.update({key: value for key, value in detail.items() if value not in (None, "", [])})
        return merged
    return row
