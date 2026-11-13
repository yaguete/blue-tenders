"""PLACSP: feed ATOM con cuerpo CODICE.

Se leen el título, el enlace, el expediente y la fecha de presentación si vienen.
Un anuncio sin título o sin identificador se rechaza: no se fabrica uno.
"""

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import date, datetime

import httpx

from app.models.opportunity import (
    Budget,
    Buyer,
    Document,
    Fact,
    FactOrigin,
    Opportunity,
    OpportunityType,
)
from app.sources.base import Source
from app.vertical import Vertical

# Feed de licitaciones de perfiles del contratante. Documentado en la
# especificación de sindicación del Ministerio; si cambia, el spike lo dirá.
FEED_URL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/"
    "licitacionesPerfilesContratanteCompleto3.atom"
)
REGIONAL_FEED_URL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1044/"
    "licitacionesPerfilesContratanteCompleto3.atom"
)
# Consultas preliminares. El fichero es la actualización del día anterior
# (datos abiertos de Hacienda, sindicacion_1403). Comprobado el 13 nov 2026.
CONSULTAS_FEED_URL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_1403/"
    "CPM_SectorPublico.atom"
)
_CLOSED = {"ADJ", "RES", "ANUL"}


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _find_text(node: ET.Element, name: str) -> str | None:
    for child in node.iter():
        if _local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def feed_root(content: bytes) -> ET.Element:
    """El feed es ATOM. Un HTML con 200 (certificado de cliente) no es un feed vacío."""
    head = content.lstrip()[:300].lower()
    if head.startswith(b"<html") or b"<html" in head:
        raise RuntimeError(
            "PLACSP ha devuelto HTML en lugar del feed ATOM: "
            "el feed exige certificado de cliente o la URL ha cambiado"
        )
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise RuntimeError(f"PLACSP: el feed no es ATOM ({exc})") from exc


def _published(entry: ET.Element) -> date | None:
    parsed = _parse_dt(_find_text(entry, "IssueDate")) or _parse_dt(_find_text(entry, "updated"))
    return parsed.date() if parsed else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class PlacspSource(Source):
    id = "placsp"
    kind = "rss"

    def __init__(self, feed_url: str = FEED_URL):
        self.feed_url = feed_url

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        url: str | None = self.feed_url
        pages = 0
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            while url and pages < 40:
                response = client.get(url)
                response.raise_for_status()
                root = feed_root(response.content)
                oldest = None
                for entry in root.iter():
                    if _local(entry.tag) != "entry":
                        continue
                    updated = _parse_dt(_find_text(entry, "updated"))
                    if updated and (oldest is None or updated < oldest):
                        oldest = updated
                    if updated and updated.date() < since:
                        continue
                    if not _cpv_ok(entry, vertical.cpv):
                        continue
                    yield {
                        "xml": ET.tostring(entry, encoding="unicode"),
                        "status": _find_text(entry, "ContractFolderStatusCode"),
                    }
                pages += 1
                if oldest and oldest.date() < since:
                    return
                url = _next(root)

    def to_tender(self, raw: dict) -> Opportunity:
        entry = ET.fromstring(raw["xml"])
        external = _find_text(entry, "ContractFolderID") or _find_text(entry, "id")
        title = _find_text(entry, "title")
        if not title:
            for node in entry.iter():
                if _local(node.tag) == "ProcurementProject":
                    title = _find_text(node, "Name")
                    break
        if not external or not title:
            raise ValueError("entrada de PLACSP sin expediente o sin título")
        link = None
        for node in entry.iter():
            if _local(node.tag) == "link" and node.attrib.get("href"):
                link = node.attrib["href"]
                break
        amount = _find_text(entry, "TaxExclusiveAmount") or _find_text(entry, "TotalAmount")
        budget = None
        if amount:
            try:
                budget = Budget(amount=float(amount), currency="EUR", amount_eur=float(amount))
            except ValueError:
                budget = None
        cpv = []
        for node in entry.iter():
            if _local(node.tag) == "ItemClassificationCode" and node.text:
                cpv.append(node.text.strip())
        party = None
        for node in entry.iter():
            if _local(node.tag) == "PartyName":
                party = _find_text(node, "Name")
                break
        nuts = _find_text(entry, "CountrySubentityCode")
        return Opportunity(
            id=Opportunity.make_id(self.id, external),
            source_id=self.id,
            external_id=external,
            url=link or "https://contrataciondelestado.es/",
            type=OpportunityType.award if (raw.get("status") or "") in _CLOSED else OpportunityType.tender,
            title=title,
            description=_find_text(entry, "summary") or _find_text(entry, "Description"),
            buyer=Buyer(name=party, country="ES") if party else None,
            country="ES",
            region=nuts,
            nuts=[nuts] if nuts else [],
            cpv=list(dict.fromkeys(cpv)),
            budget=budget,
            language="es",
            deadline_at=_submission_deadline(entry),
            published_at=_published(entry),
            documents=_documents(entry, link),
            call_id=external,
            dedupe_key=external,
            raw={"external_id": external, "procedure": external, "procedure-identifier": external},
        )


_PLIEGO_NAMES = {
    "DOC_PCAP": "Administrative specifications",
    "PCAP": "Administrative specifications",
    "DOC_PPT": "Technical specifications",
    "PPT": "Technical specifications",
}
_DOC_NODES = {
    "LegalDocumentReference",
    "AdditionalDocumentReference",
    "CallForTendersDocumentReference",
}


def _documents(entry: ET.Element, link: str | None) -> list[Document]:
    """El anuncio y los pliegos que la propia entrada ya enlaza (misma plataforma)."""
    documents = [Document(url=link, name="Notice", kind="html", access="fetch")] if link else []
    seen = {link} if link else set()
    for node in entry.iter():
        if _local(node.tag) not in _DOC_NODES:
            continue
        code = None
        uri = None
        for child in node.iter():
            if _local(child.tag) in {"DocumentTypeCode", "DocumentType"} and child.text:
                code = child.text.strip()
            if _local(child.tag) == "URI" and child.text and child.text.strip().startswith("http"):
                uri = child.text.strip()
        if not uri or uri in seen:
            continue
        seen.add(uri)
        documents.append(
            Document(
                url=uri,
                name=_PLIEGO_NAMES.get(code or "", code or "Tender document"),
                kind="pliego",
                access="fetch",
            )
        )
    return documents


def _next(root: ET.Element) -> str | None:
    for node in root:
        if _local(node.tag) == "link" and node.attrib.get("rel") == "next":
            return node.attrib.get("href")
    return None


def _cpv_ok(entry: ET.Element, wanted: list[str]) -> bool:
    if not wanted:
        return True
    codes = [
        node.text.strip()
        for node in entry.iter()
        if _local(node.tag) == "ItemClassificationCode" and node.text and node.text.strip()
    ]
    if not codes:
        return True
    return any(code.startswith(prefix[:8]) or prefix.startswith(code[:8]) for code in codes for prefix in wanted)


def _submission_deadline(entry: ET.Element) -> datetime | None:
    period = None
    for node in entry.iter():
        if _local(node.tag) == "TenderSubmissionDeadlinePeriod":
            period = node
            break
    node = period if period is not None else entry
    day = _find_text(node, "EndDate") or _find_text(node, "DueDate")
    clock = _find_text(node, "EndTime") if period is not None else None
    if day and clock and "T" not in day:
        return _parse_dt(f"{day}T{clock}")
    return _parse_dt(day)


class PlacspRegionalSource(PlacspSource):
    id = "placsp-regional"

    def __init__(self):
        super().__init__(REGIONAL_FEED_URL)


class PlacspConsultasSource(PlacspSource):
    """Consulta previa al pliego. No es la licitación: el plazo de respuesta no es un cierre."""

    id = "placsp-consultas"
    # Un día sin consultas del sector no es una fuente caída. Un HTML sí rompe el feed.
    volume_alert = False

    def __init__(self):
        super().__init__(CONSULTAS_FEED_URL)

    def to_tender(self, raw: dict) -> Opportunity:
        entry = ET.fromstring(raw["xml"])
        external = _find_text(entry, "PreliminaryMarketConsultationID") or _find_text(entry, "id")
        title = _find_text(entry, "title") or _find_text(entry, "ConsultationName")
        if not title:
            for node in entry.iter():
                if _local(node.tag) == "ProcurementProject":
                    title = _find_text(node, "Name")
                    break
        if not external or not title:
            raise ValueError("consulta de PLACSP sin identificador o sin título")
        link = None
        for node in entry.iter():
            if _local(node.tag) == "link" and node.attrib.get("href"):
                link = node.attrib["href"]
                break
        published = _parse_dt(_find_text(entry, "updated")) or _parse_dt(_find_text(entry, "IssueDate"))
        if published is None:
            raise ValueError(f"consulta de PLACSP {external} sin fecha")
        party = None
        for node in entry.iter():
            if _local(node.tag) == "PartyName":
                party = _find_text(node, "Name")
                break
        cpv = [
            node.text.strip()
            for node in entry.iter()
            if _local(node.tag) == "ItemClassificationCode" and node.text and node.text.strip()
        ]
        nuts = _find_text(entry, "CountrySubentityCode")
        return Opportunity(
            id=Opportunity.make_id(self.id, external),
            source_id=self.id,
            external_id=external,
            url=link or "https://contrataciondelestado.es/",
            type=OpportunityType.prior_information_notice,
            title=title,
            description=_find_text(entry, "summary"),
            buyer=Buyer(name=party, country="ES") if party else None,
            country="ES",
            region=nuts,
            nuts=[nuts] if nuts else [],
            cpv=list(dict.fromkeys(cpv)),
            language="es",
            published_at=published.date(),
            documents=_consultation_documents(entry, link),
            facts=_response_fact(entry, link),
            raw={"external_id": external},
        )


def _response_fact(entry: ET.Element, link: str | None) -> list[Fact]:
    """El límite para contestar va citado. No se convierte en plazo de la licitación."""
    limit = _find_text(entry, "LimitDate")
    if not limit:
        return []
    parsed = _parse_dt(limit)
    return [
        Fact(
            field="response_by",
            value=parsed.date().isoformat() if parsed else None,
            origin=FactOrigin.source,
            confidence=0.9,
            quote=limit,
            document_url=link,
        )
    ]


def _consultation_documents(entry: ET.Element, link: str | None) -> list[Document]:
    documents = [Document(url=link, name="Notice", kind="html", access="fetch")] if link else []
    seen = {link} if link else set()
    for node in entry.iter():
        if _local(node.tag) != "GeneralDocument":
            continue
        uri = _find_text(node, "URI")
        if not uri or not uri.startswith("http") or uri in seen:
            continue
        seen.add(uri)
        documents.append(
            Document(
                url=uri,
                name=_find_text(node, "FileName") or "Consultation document",
                kind="html",
                access="fetch",
            )
        )
    return documents
