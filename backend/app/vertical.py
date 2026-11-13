"""Carga la definición de un vertical desde config/verticals/<id>.yaml."""

from functools import lru_cache

import yaml
from pydantic import BaseModel

from app.settings import settings


class Subsector(BaseModel):
    id: str
    name: str
    enabled: bool = False
    keywords: list[str] = []
    # Vocabulario solo para el historial de proyectos (CORDIS). El prefiltro no lo lee.
    project_keywords: list[str] = []
    exclude_keywords: list[str] = []


class TrackRecordConfig(BaseModel):
    """Umbrales del historial. Viven en el YAML del vertical, no en el código."""

    min_text_similarity: float = 0.15
    awards_min_text_similarity: float = 0.14
    awards_min_cpv_digits: int = 5
    min_shared_tokens: int = 2
    limit: int = 30


class Vertical(BaseModel):
    id: str
    name: str
    subsectors: list[Subsector]
    cpv: list[str] = []
    geographies: dict = {}
    opportunity_types: list[str] = []
    languages: list[str] = []
    # Términos con los que una fuente sabe buscar, por subsector. El prefiltro no los lee:
    # el adaptador marca `_source_subsectors` cuando casa uno.
    search_terms: dict[str, dict[str, list[str]]] = {}
    track_record: TrackRecordConfig = TrackRecordConfig()

    @property
    def active_subsectors(self) -> list[Subsector]:
        return [s for s in self.subsectors if s.enabled]


@lru_cache
def load_vertical(vertical_id: str | None = None) -> Vertical:
    vid = vertical_id or settings.vertical
    path = settings.verticals_dir / f"{vid}.yaml"
    with path.open() as f:
        return Vertical(**yaml.safe_load(f))
