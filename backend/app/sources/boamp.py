"""BOAMP. Los datos abiertos de la DILA se publican con Licence Ouverte 2.0.

Fuera del cron hasta confirmar en la ficha del dataset que esa es la licencia de
este recurso concreto. La búsqueda del API no es de frase exacta: el prefiltro
sigue haciendo falta.
"""

from collections.abc import Iterable
from datetime import date, datetime

import httpx

from app.models.opportunity import Opportunity, OpportunityType
from app.sources.base import Source
from app.vertical import Vertical

SEARCH_URL = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"


class BoampSource(Source):
    id = "boamp"
    kind = "api"

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del vertical
        with httpx.Client(timeout=40) as client:
            response = client.get(
                SEARCH_URL,
                params={"where": f"dateparution >= date'{since.isoformat()}'", "limit": 100},
            )
            response.raise_for_status()
            payload = response.json()
        yield from payload.get("results") or []

    def to_tender(self, raw: dict) -> Opportunity:
        ident = str(raw.get("idweb") or raw.get("filename") or "")
        title = raw.get("objet") or raw.get("nomacheteur")
        if not ident or not title:
            raise ValueError("anuncio BOAMP sin id o sin objeto")
        end = raw.get("datelimitereponse")
        deadline = None
        if end:
            try:
                deadline = datetime.fromisoformat(str(end))
            except ValueError:
                deadline = None
        return Opportunity(
            id=Opportunity.make_id(self.id, ident),
            source_id=self.id,
            external_id=ident,
            url=raw.get("url_avis") or f"https://www.boamp.fr/avis/detail/{ident}",
            type=OpportunityType.tender,
            title=str(title),
            description=raw.get("objet"),
            country="FR",
            language="fr",
            deadline_at=deadline,
            raw=raw,
        )
