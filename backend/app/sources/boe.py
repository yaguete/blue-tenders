"""Sumario del BOE. Señal temprana: las bases salen antes que la convocatoria en BDNS.

No convierte una frase en fecha. El anuncio entra como información previa.
Un 404 es un día sin diario (domingo o festivo), no un fallo de la fuente.
Una formalización o adjudicación no entra: cierra un proceso, no anuncia una convocatoria.
"""

from collections.abc import Iterable
from datetime import date, timedelta

import httpx

from app.keywords import keyword_words, mentions
from app.keywords import tokens as text_tokens
from app.models.opportunity import (
    Document,
    Fact,
    FactOrigin,
    NoticeKind,
    Opportunity,
    OpportunityType,
)
from app.sources.base import Source
from app.vertical import Vertical

SUMMARY_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/{}"


def _rows(value) -> list[dict]:
    """El sumario mezcla listas y objetos. Una cadena (clave suelta) no es un bloque."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def pdf_url(raw: dict) -> str | None:
    """El sumario trae el PDF en `url_pdf.texto`. A veces el campo ya es la URL."""
    value = raw.get("url_pdf")
    if isinstance(value, str) and value.startswith("http"):
        return value
    if isinstance(value, dict):
        text = value.get("texto")
        if isinstance(text, str) and text.startswith("http"):
            return text
    return None


def items(payload: dict) -> list[dict]:
    found = []
    for day in _rows(((payload.get("data") or {}).get("sumario") or {}).get("diario")):
        for section in _rows(day.get("seccion")):
            for department in _rows(section.get("departamento")):
                epigraphs = _rows(department.get("epigrafe"))
                blocks = epigraphs or [department]
                for block in blocks:
                    found.extend(_rows(block.get("item")))
    return found


def is_award(title: str) -> bool:
    """Formalizaciones y adjudicaciones en el BOE empiezan por un encabezado fijo.

    Igual que BOAMP descarta `ATTRIBUTION` y Find a Tender los `tag` de award:
    el proceso ya cerró, no es señal de lo que viene.
    """
    normalized = (title or "").strip().lower()
    return normalized.startswith(("anuncio de formalización de contrato", "anuncio de adjudicaci"))


class BoeSource(Source):
    id = "boe"
    kind = "api"
    volume_alert = False

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        words = [keyword_words(keyword) for sub in vertical.active_subsectors for keyword in sub.keywords]
        day = since
        today = date.today()
        with httpx.Client(timeout=40, headers={"Accept": "application/json", "User-Agent": "blue-tender/1.0"}) as client:
            while day <= today:
                response = client.get(SUMMARY_URL.format(day.strftime("%Y%m%d")))
                if response.status_code == 404:
                    day += timedelta(days=1)
                    continue
                response.raise_for_status()
                for item in items(response.json()):
                    title = str(item.get("titulo") or "")
                    if is_award(title):
                        continue
                    blob = text_tokens(f"{title} {item.get('texto') or ''}")
                    if any(mentions(blob, keyword) for keyword in words):
                        row = dict(item)
                        row["published_at"] = day.isoformat()
                        yield row
                day += timedelta(days=1)

    def to_tender(self, raw: dict) -> Opportunity:
        ident = str(raw.get("identificador") or "")
        title = raw.get("titulo")
        if not ident or not title:
            raise ValueError("disposición del BOE sin identificador o sin título")
        url = raw.get("url_html") or f"https://www.boe.es/diario_boe/txt.php?id={ident}"
        published = str(raw.get("published_at") or "")[:10]
        pdf = pdf_url(raw)
        documents = [Document(url=pdf, name="Notice (PDF)", kind="notice", access="fetch")] if pdf else []
        facts = [
            Fact(
                field="notice_pdf",
                value=pdf,
                origin=FactOrigin.source,
                confidence=0.95,
                document_url=pdf,
            )
        ] if pdf else []
        return Opportunity(
            id=Opportunity.make_id(self.id, ident),
            source_id=self.id,
            external_id=ident,
            url=str(url),
            type=OpportunityType.prior_information_notice,
            notice=NoticeKind.pin,
            title=str(title),
            description=raw.get("texto"),
            country="ES",
            language="es",
            published_at=date.fromisoformat(published) if published else None,
            documents=documents,
            facts=facts,
            raw=raw,
        )
