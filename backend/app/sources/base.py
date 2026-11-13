from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date

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


class Source(ABC):
    """Un adaptador por fuente. Ver backend/app/sources/README.md."""

    id: str
    kind: str  # api | rss | html | pdf

    @abstractmethod
    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        """Registros crudos publicados desde `since`, prefiltrados si la fuente lo permite."""

    @abstractmethod
    def to_tender(self, raw: dict) -> Tender:
        """Convierte un registro crudo al modelo canónico."""

    def to_opportunity(self, raw: dict) -> Tender:
        return self.to_tender(raw)
