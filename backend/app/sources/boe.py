"""Sumario del BOE. Señal temprana: las bases salen antes que la convocatoria en BDNS.

No convierte una frase en fecha. El anuncio entra como información previa.
Un 404 es un día sin diario (domingo o festivo), no un fallo de la fuente.
"""

from collections.abc import Iterable
from datetime import date, timedelta

import httpx

from app.keywords import keyword_words, mentions
from app.keywords import tokens as text_tokens
from app.models.opportunity import NoticeKind, Opportunity, OpportunityType
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
                    blob = text_tokens(f"{item.get('titulo') or ''} {item.get('texto') or ''}")
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
            raw=raw,
        )
