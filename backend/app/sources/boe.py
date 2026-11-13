"""Sumario del BOE. Señal temprana: las bases salen antes que la convocatoria en BDNS.

No convierte una frase en fecha. El anuncio entra como información previa.
"""

from collections.abc import Iterable
from datetime import date

import httpx

from app.keywords import keyword_words, mentions
from app.keywords import tokens as text_tokens
from app.models.opportunity import NoticeKind, Opportunity, OpportunityType
from app.sources.base import Source
from app.vertical import Vertical

SUMMARY_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/{}"


class BoeSource(Source):
    id = "boe"
    kind = "api"

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del since
        words = [keyword_words(keyword) for sub in vertical.active_subsectors for keyword in sub.keywords]
        with httpx.Client(timeout=40, headers={"Accept": "application/json"}) as client:
            response = client.get(SUMMARY_URL.format(date.today().strftime("%Y%m%d")))
            response.raise_for_status()
            payload = response.json()
        for item in _items(payload):
            blob = text_tokens(f"{item.get('titulo') or ''} {item.get('texto') or ''}")
            if any(mentions(blob, keyword) for keyword in words):
                yield item

    def to_tender(self, raw: dict) -> Opportunity:
        ident = str(raw.get("identificador") or "")
        title = raw.get("titulo")
        if not ident or not title:
            raise ValueError("disposición del BOE sin identificador o sin título")
        url = raw.get("url_html") or f"https://www.boe.es/diario_boe/txt.php?id={ident}"
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
            raw=raw,
        )


def _items(payload: dict) -> list[dict]:
    diario = ((payload.get("data") or {}).get("sumario") or {}).get("diario") or []
    if isinstance(diario, dict):
        diario = [diario]
    found = []
    for day in diario:
        for section in day.get("seccion") or []:
            sections = section if isinstance(section, list) else [section]
            for block in sections:
                for dept in block.get("departamento") or []:
                    departments = dept if isinstance(dept, list) else [dept]
                    for department in departments:
                        for item in department.get("item") or []:
                            rows = item if isinstance(item, list) else [item]
                            found.extend(row for row in rows if isinstance(row, dict))
    return found
