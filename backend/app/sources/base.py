from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date

from app.keywords import keyword_words, mentions, tokens
from app.models.tender import Tender
from app.vertical import Vertical

# Clave que un adaptador puede añadir al registro crudo cuando su fuente sabe buscar por texto
# completo: la lista de subsectores cuyo vocabulario encontró en el registro entero. El
# prefiltro y el clasificador solo ven el título y la descripción, así que sin esta marca
# tirarían un anuncio que menciona "offshore wind" en la página 3.
SOURCE_SUBSECTORS = "_source_subsectors"


def source_subsectors(raw: dict | None) -> list[str]:
    """Subsectores que la fuente encontró en el texto completo del registro (o lista vacía)."""
    value = (raw or {}).get(SOURCE_SUBSECTORS)
    return [str(v) for v in value] if isinstance(value, list) else []


def search_term_in(text: str, term: str) -> bool:
    """Si el término que la fuente buscó aparece de verdad en el texto del registro.

    El buscador de algunas fuentes casa palabra a palabra: en TenderNed, "wind op zee" trae
    cualquier texto con "op" o "zee" (Zeeland, Scheveningen). La marca de subsector solo
    puede fiarse del buscador si el término está aquí, con las mismas reglas de palabras
    completas y cercanía que el prefiltro.
    """
    return mentions(tokens(text), keyword_words(term))


class Source(ABC):
    """Un adaptador por fuente. Ver backend/app/sources/README.md."""

    id: str
    kind: str  # api | rss | html | pdf
    # False en las que buscan por término: un cero es un día sin sector, no una fuente caída.
    volume_alert: bool = True

    @abstractmethod
    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        """Registros crudos publicados desde `since`, prefiltrados si la fuente lo permite."""

    @abstractmethod
    def to_tender(self, raw: dict) -> Tender:
        """Convierte un registro crudo al modelo canónico."""

    def to_opportunity(self, raw: dict) -> Tender:
        return self.to_tender(raw)
