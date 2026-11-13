"""Prioridad entre fuentes. Vive en config/sources.yaml, no en el pipeline."""

from functools import lru_cache

import yaml

from app.settings import settings


@lru_cache
def source_priority() -> dict[str, int]:
    path = settings.config_dir / "sources.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(key): int(value) for key, value in (data.get("priority") or {}).items()}
