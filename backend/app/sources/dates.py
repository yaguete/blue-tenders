"""Lee una fecha escrita en la página. No inventa el día si el texto no es una fecha."""

import re
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import yaml

from app.settings import settings

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@lru_cache
def month_names() -> dict[str, list[str]]:
    path = settings.config_dir / "months.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(key): [str(name) for name in names] for key, names in data.items()}


def parse_when(text: str | None, language: str, formats: list[str], timezone: str) -> datetime | None:
    """Inicio del día en `timezone` si la página no da hora. None si no es una fecha."""
    raw = " ".join(str(text or "").split())
    if not raw:
        return None
    iso = _iso(raw)
    if iso is not None:
        if iso.tzinfo is None:
            return iso.replace(tzinfo=ZoneInfo(timezone))
        return iso
    numbered, replaced = _number_months(raw, language)
    zone = ZoneInfo(timezone)
    for fmt in formats:
        candidate = numbered if replaced else raw
        pattern = fmt.replace("%B", "%m").replace("%b", "%m") if replaced else fmt
        if language in {"es", "pt"}:
            candidate = re.sub(r"\bde\b", " ", candidate)
            candidate = " ".join(candidate.split())
            pattern = pattern.replace(" de ", " ")
        try:
            parsed = datetime.strptime(candidate, pattern)
        except ValueError:
            continue
        return parsed.replace(tzinfo=zone)
    return _embedded(numbered if replaced else raw, replaced, language, zone)


def _embedded(text: str, already_numbered: bool, language: str, zone: ZoneInfo) -> datetime | None:
    """Una fecha escrita dentro de una frase. Se queda con la última: suele ser el cierre."""
    numbered = text if already_numbered else _number_months(text, language)[0]
    found = list(
        re.finditer(
            r"(\d{1,2})\.?\s+(\d{2})\s+(\d{4})(?:\D{0,16}(\d{1,2}):(\d{2}))?",
            numbered,
        )
    )
    if not found:
        return None
    day, month, year, hour, minute = found[-1].groups()
    try:
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            tzinfo=zone,
        )
    except ValueError:
        return None


def _iso(text: str) -> datetime | None:
    candidate = text.replace("Z", "+00:00")
    if "T" not in candidate and len(candidate) > 10:
        return None
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _number_months(text: str, language: str) -> tuple[str, bool]:
    names = month_names()
    table = list(enumerate(names.get(language) or [], start=1))
    table += list(enumerate(names.get("abbr") or [], start=1))
    replaced = False
    words = text.split()
    out = []
    for word in words:
        bare = _WORD.fullmatch(word.strip(".,"))
        key = bare.group(0).lower() if bare else ""
        month = next((index for index, name in table if name.lower() == key), None)
        if month is None:
            out.append(word)
            continue
        replaced = True
        out.append(f"{month:02d}")
    return " ".join(out), replaced
