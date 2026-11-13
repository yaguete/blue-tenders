"""Reglas de programa, cuencas y convocatorias curadas. Todo sale de config/."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.settings import settings


class ProgrammeRule(BaseModel):
    id: str
    programme_id: str
    type_of_action: str | None = None
    label: str
    consortium_required: bool | None = None
    consortium_min_partners: int | None = None
    consortium_min_countries: int | None = None
    cofunding_min: float | None = None
    cofunding_max: float | None = None
    eligible_entity_types: list[str] = []
    eligible_countries: list[str] = []
    legal_basis: str | None = None
    notes: str | None = None


class FunderProfile(BaseModel):
    id: str
    name: str
    kind: str
    url: str
    summary: str
    instruments: list[str] = []
    geographies: list[str] = []
    subsectors: list[str] = []
    ticket_min_eur: float | None = None
    ticket_max_eur: float | None = None
    is_directory_listed: bool = True
    last_verified: str | None = None


@lru_cache
def programme_rules() -> tuple[ProgrammeRule, ...]:
    folder = settings.config_dir / "programmes"
    rules = []
    for path in sorted(folder.glob("*.yaml")):
        rules.append(ProgrammeRule(**yaml.safe_load(path.read_text(encoding="utf-8"))))
    return tuple(rules)


def rule_for(programme_id: str | None, type_of_action: str | None) -> ProgrammeRule | None:
    if not programme_id:
        return None
    action = (type_of_action or "").upper()
    exact = None
    fallback = None
    for rule in programme_rules():
        if rule.programme_id != programme_id and rule.id != programme_id:
            continue
        if rule.type_of_action and rule.type_of_action.upper() == action:
            exact = rule
        elif rule.type_of_action is None:
            fallback = rule
    return exact or fallback


@lru_cache
def sea_basin_prefixes() -> tuple[tuple[str, tuple[str, ...]], ...]:
    path = settings.config_dir / "geographies" / "sea-basins.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pairs = [(k, tuple(v)) for k, v in (raw.get("prefixes") or {}).items()]
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return tuple(pairs)


@lru_cache
def sea_basin_names() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Frases de búsqueda de cada cuenca. Viven en el YAML, no en el buscador."""
    path = settings.config_dir / "geographies" / "sea-basins.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = raw.get("names") or {}
    return tuple(
        (str(basin), tuple(str(phrase) for phrase in phrases))
        for basin, phrases in names.items()
    )


def basins_for_nuts(codes: list[str]) -> list[str]:
    found: list[str] = []
    for code in codes:
        for prefix, basins in sea_basin_prefixes():
            if code.startswith(prefix):
                for basin in basins:
                    if basin not in found:
                        found.append(basin)
                break
    return found


def sdgs_for(vertical_id: str, subsectors: list[str]) -> list[int]:
    path = settings.verticals_dir / f"{vertical_id}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mapping = data.get("sdg_by_subsector") or {}
    out: list[int] = []
    for sub in subsectors:
        for sdg in mapping.get(sub) or []:
            if sdg not in out:
                out.append(sdg)
    return out


def funder_profiles() -> list[FunderProfile]:
    folder = settings.config_dir / "funders"
    if not folder.exists():
        return []
    profiles = []
    for path in sorted(folder.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        rows = data if isinstance(data, list) else [data]
        profiles.extend(FunderProfile(**row) for row in rows)
    return profiles


def read_yaml_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return list(data)
