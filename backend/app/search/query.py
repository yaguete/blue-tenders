"""Filtros inclusivos: un campo vacío no esconde la oportunidad, salvo exclude_unknown."""

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache

from app.keywords import keyword_words, plain, tokens
from app.models.opportunity import Opportunity, OpportunityStatus, compute_status

# «Se cierra pronto» son 60 días: dos meses justos, contados en días como el resto de plazos.
CLOSING_SOON_DAYS = 60


@dataclass
class SearchFilters:
    q: str | None = None
    kind: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    subsector: list[str] = field(default_factory=list)
    programme_id: list[str] = field(default_factory=list)
    country: list[str] = field(default_factory=list)
    entity_type: str | None = None
    consortium_required: bool | None = None
    mission_ocean: bool | None = None
    amount_min: float | None = None
    amount_max: float | None = None
    cofunding_min: float | None = None
    sea_basin: list[str] = field(default_factory=list)
    trl: int | None = None
    closing_within_days: int | None = None
    deadline: list[str] = field(default_factory=list)
    exclude_unknown: bool = False
    limit: int = 20
    offset: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.country, str):
            self.country = [self.country] if self.country else []


@dataclass
class Facet:
    value: str
    count: int
    unknown: int = 0


def search_opportunities(
    items: list[Opportunity],
    filters: SearchFilters,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    fresh = []
    for item in items:
        if not item.searchable():
            continue
        item.status = compute_status(item, today)
        fresh.append(item)

    matched = [item for item in fresh if _match(item, filters, today)]
    in_tabs = [item for item in fresh if _match(item, replace(filters, kind=[]), today)]
    in_deadlines = [item for item in fresh if _match(item, replace(filters, deadline=[]), today)]
    in_countries = [item for item in fresh if _match(item, replace(filters, country=[]), today)]
    kind_counts: dict[str, int] = {}
    for item in in_tabs:
        value = item.kind.value if item.kind else None
        if value:
            kind_counts[value] = kind_counts.get(value, 0) + 1
    deadline_counts: dict[str, int] = {}
    for item in in_deadlines:
        bucket = deadline_bucket(item, today)
        deadline_counts[bucket] = deadline_counts.get(bucket, 0) + 1
    if filters.q:
        matched.sort(key=lambda item: (-_score(item, filters.q or ""), item.id))
    else:
        matched.sort(key=lambda item: (_deadline_key(item), item.id))

    return {
        "total": len(matched),
        "counts": {"all": len(in_tabs), "kind": kind_counts, "deadline": deadline_counts},
        "unknown": _unknown_counts(fresh, filters),
        "items": matched[filters.offset : filters.offset + filters.limit],
        "facets": {
            "kind": _facet(fresh, lambda item: item.kind.value if item.kind else None),
            "status": _facet(fresh, lambda item: item.status.value if item.status else None),
            "subsector": _facet_list(fresh, lambda item: item.subsectors),
            "programme_id": _facet(fresh, lambda item: item.programme_id),
            "country": _facet(in_countries, lambda item: item.country),
            "country_missing": sum(1 for item in in_countries if not item.country),
        },
    }


def _deadline_key(item: Opportunity) -> datetime:
    if item.deadline_at is None:
        return datetime.max.replace(tzinfo=UTC)
    if item.deadline_at.tzinfo is None:
        return item.deadline_at.replace(tzinfo=UTC)
    return item.deadline_at


def _query_words(q: str) -> list[str]:
    seen: list[str] = []
    for word in tokens(q):
        if word not in seen:
            seen.append(word)
    return seen


# Palabras que no dicen de qué va la convocatoria. Una búsqueda no puede exigirlas.
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "del", "las", "los", "una", "unos", "por", "con", "que", "para",
}
# Terminaciones que distinguen género y número, no otra palabra.
_ENDINGS = {"", "o", "a", "os", "as", "es", "s"}


def _haystack(item: Opportunity) -> str:
    return " ".join([item.title, item.title_en or "", item.summary_en or "", item.description or ""])


def _significant(words: list[str]) -> list[str]:
    return [word for word in words if len(word) >= 3 and word not in _STOP]


def _same_ending(left: str, right: str) -> bool:
    shared = 0
    for a, b in zip(left, right):
        if a != b:
            break
        shared += 1
    return shared >= 5 and left[shared:] in _ENDINGS and right[shared:] in _ENDINGS


def _word_hit(query_word: str, token: str) -> bool:
    """La palabra buscada casa con un token, sin mirar mayúsculas (ya van en minúscula).

    También casa el plural, el género («eólico» con «eólica») y un prefijo de 5 letras
    o más («decomm» con «decommissioning»). «ops» no casa con «workshops»: se comparan
    palabras, no trozos de una palabra.
    """
    if query_word == token or token in {query_word + "s", query_word + "es"}:
        return True
    if query_word in {token + "s", token + "es"}:
        return True
    if len(query_word) >= 5 and len(token) >= 5 and _same_ending(query_word, token):
        return True
    return len(query_word) >= 5 and token.startswith(query_word)


def _covers(query_words: list[str], keyword_word: str) -> bool:
    if keyword_word.endswith("*"):
        prefix = keyword_word[:-1]
        return any(word.startswith(prefix) or (prefix.startswith(word) and len(word) >= 5) for word in query_words)
    return any(_word_hit(word, keyword_word) for word in query_words)


def _concept_subsectors(query: list[str]) -> set[str]:
    """Subsectores cuyo vocabulario está en la búsqueda, no solo en el texto del anuncio."""
    from app.vertical import load_vertical

    found = set()
    for subsector in load_vertical().active_subsectors:
        for keyword in subsector.keywords:
            words = keyword_words(keyword)
            if not words:
                continue
            whole = all(_covers(query, word) for word in words)
            distinctive = any(
                len(word) >= 6 and _covers([word], keyword_word)
                for word in query
                for keyword_word in words
            )
            if whole or distinctive:
                found.add(subsector.id)
                break
    return found


def _title_sector_hits(item: Opportunity, sectors: set[str]) -> int:
    """Cuántas palabras del subsector nombra el título. Sirve para ordenar, no para decidir."""
    from app.vertical import load_vertical

    title = tokens(item.title_en or item.title)
    found: set[str] = set()
    for subsector in load_vertical().active_subsectors:
        if subsector.id not in sectors:
            continue
        for keyword in subsector.keywords:
            for word in keyword_words(keyword):
                if word.endswith("*") or len(word) < 4 or word in found:
                    continue
                if any(_word_hit(word, token) for token in title):
                    found.add(word)
    return len(found)


def _hits(query: list[str], text_tokens: list[str]) -> list[str]:
    return [word for word in query if any(_word_hit(word, token) for token in text_tokens)]


@dataclass(frozen=True)
class _KnownPhrase:
    """Una frase del vertical o de una cuenca. Las palabras van en el orden en que se escribe."""

    words: tuple[str, ...]
    subsector: str | None = None
    basin: str | None = None


@dataclass(frozen=True)
class _Chunk:
    words: tuple[str, ...]
    subsectors: tuple[str, ...] = ()
    basins: tuple[str, ...] = ()

    @property
    def concept(self) -> bool:
        return bool(self.subsectors or self.basins)


@lru_cache(maxsize=1)
def _known_phrases() -> tuple[_KnownPhrase, ...]:
    """Conceptos de varias palabras: keywords del vertical y nombres de cuenca."""
    from app.catalog import sea_basin_names
    from app.vertical import load_vertical

    found: list[_KnownPhrase] = []
    for subsector in load_vertical().active_subsectors:
        for keyword in subsector.keywords:
            words = tuple(
                word
                for word in keyword_words(keyword)
                if word.endswith("*") or (len(word) >= 3 and word not in _STOP)
            )
            if len(words) >= 2:
                found.append(_KnownPhrase(words, subsector=subsector.id))
    for basin, phrases in sea_basin_names():
        for phrase in phrases:
            words = tuple(_significant(tokens(phrase)))
            if len(words) >= 2:
                found.append(_KnownPhrase(words, basin=basin))
    return tuple(found)


def _query_word_covers(query_word: str, keyword_word: str) -> bool:
    if keyword_word.endswith("*"):
        prefix = keyword_word[:-1]
        return len(prefix) >= 4 and (
            query_word.startswith(prefix) or (prefix.startswith(query_word) and len(query_word) >= 5)
        )
    return _word_hit(query_word, keyword_word) or _word_hit(keyword_word, query_word)


def _chunks(query: list[str]) -> list[_Chunk]:
    """Parte la búsqueda en conceptos conocidos y palabras sueltas, sin solaparse.

    «offshore wind farm» se queda en el concepto «offshore wind» y la palabra «farm».
    No se traga «farm» dentro de otra keyword solo porque use las mismas palabras.
    """
    known = _known_phrases()
    chunks: list[_Chunk] = []
    index = 0
    while index < len(query):
        best = 0
        matched: list[_KnownPhrase] = []
        for concept in known:
            size = len(concept.words)
            if size <= best or index + size > len(query):
                continue
            span = query[index : index + size]
            pairs = zip(span, concept.words, strict=True)
            if all(_query_word_covers(word, kw) for word, kw in pairs):
                if size > best:
                    best = size
                    matched = [concept]
                else:
                    matched.append(concept)
        if not matched:
            chunks.append(_Chunk((query[index],)))
            index += 1
            continue
        chunks.append(
            _Chunk(
                tuple(query[index : index + best]),
                tuple(dict.fromkeys(item.subsector for item in matched if item.subsector)),
                tuple(dict.fromkeys(item.basin for item in matched if item.basin)),
            )
        )
        index += best
    return chunks


def _content(text_tokens: list[str]) -> list[str]:
    return [token for token in text_tokens if len(token) >= 3 and token not in _STOP]


def _phrase(text_tokens: list[str], words: list[str]) -> bool:
    """Las palabras van seguidas, en ese orden. «north sea» no casa con «north … sea»."""
    content = _content(text_tokens)
    if len(words) == 1:
        return any(_word_hit(words[0], token) for token in content)
    size = len(words)
    if len(content) < size:
        return False
    for start in range(len(content) - size + 1):
        if all(_word_hit(words[offset], content[start + offset]) for offset in range(size)):
            return True
    return False


def _concept_hit(chunk: _Chunk, item: Opportunity, text: list[str]) -> bool:
    if _phrase(text, list(chunk.words)):
        return True
    if any(subsector in item.subsectors for subsector in chunk.subsectors):
        return True
    return any(basin in item.sea_basins for basin in chunk.basins)


def _loose_score(item: Opportunity, query: list[str]) -> float:
    matched = _hits(query, tokens(_haystack(item)))
    sectors = set(item.subsectors) & _concept_subsectors(query)
    if not matched:
        if not sectors:
            return 0
        # Sin la palabra en el texto, primero los títulos que sí nombran el subsector.
        return 0.35 + 0.05 * min(_title_sector_hits(item, sectors), 4)
    coverage = len(matched) / len(query)
    title = tokens(item.title_en or item.title)
    in_title = len(_hits(matched, title))
    if in_title == len(query):
        title_bonus = 0.5
    elif in_title:
        title_bonus = 0.2
    else:
        title_bonus = 0
    return coverage + title_bonus + 0.15 * (item.relevance or 0)


def _loose_reason(item: Opportunity, query: list[str]) -> str | None:
    present = _hits(query, tokens(_haystack(item)))
    if present:
        return "Matches " + ", ".join(present)
    concepts = set(item.subsectors) & _concept_subsectors(query)
    if concepts:
        return "Classified in " + ", ".join(sorted(concepts))
    return None


def _phrase_score(item: Opportunity, query: list[str]) -> tuple[float, str | None]:
    """Varias palabras no se buscan sueltas.

    Cada concepto conocido («north sea», «offshore wind») tiene que aparecer seguido
    en el texto, o la convocatoria ya está clasificada en esa cuenca o ese subsector.
    Si la búsqueda no tiene ningún concepto, las palabras tienen que ir seguidas.
    Una palabra suelta al lado de un concepto («mid», «farm») ordena, no mete otra ficha.
    """
    chunks = _chunks(query)
    text = tokens(_haystack(item))
    title = tokens(item.title_en or item.title)
    concepts = [chunk for chunk in chunks if chunk.concept]
    if not concepts:
        if not _phrase(text, query):
            return 0, None
        bonus = 0.5 if _phrase(title, query) else 0
        return 1 + bonus + 0.15 * (item.relevance or 0), "Matches " + " ".join(query)

    if not all(_concept_hit(chunk, item, text) for chunk in concepts):
        return 0, None

    in_text = [chunk for chunk in concepts if _phrase(text, list(chunk.words))]
    if not in_text:
        sectors = {
            subsector
            for chunk in concepts
            for subsector in chunk.subsectors
            if subsector in item.subsectors
        }
        ids: list[str] = []
        for chunk in concepts:
            ids.extend(subsector for subsector in chunk.subsectors if subsector in item.subsectors)
            ids.extend(basin for basin in chunk.basins if basin in item.sea_basins)
        reason = "Classified in " + ", ".join(dict.fromkeys(ids))
        score = 0.35 + 0.05 * min(_title_sector_hits(item, sectors), 4)
        return score, reason

    labels = [" ".join(chunk.words) for chunk in in_text]
    for chunk in chunks:
        if chunk.concept:
            continue
        if all(any(_word_hit(word, token) for token in _content(text)) for word in chunk.words):
            labels.append(" ".join(chunk.words))
    in_title = sum(1 for chunk in concepts if _phrase(title, list(chunk.words)))
    if in_title == len(concepts):
        bonus = 0.5
    elif in_title:
        bonus = 0.2
    else:
        bonus = 0
    coverage = len(in_text) / len(concepts)
    return coverage + bonus + 0.15 * (item.relevance or 0), "Matches " + ", ".join(labels)


def _score(item: Opportunity, q: str) -> float:
    raw = _query_words(q)
    query = _significant(raw)
    if not query:
        return 0
    needle = plain(q).strip()
    for ident in (item.external_id, item.topic_id, item.call_id):
        if ident and needle == plain(ident):
            return 10
    if len(query) == 1:
        return _loose_score(item, query)
    return _phrase_score(item, query)[0]


def match_reason(item: Opportunity, q: str) -> str | None:
    query = _significant(_query_words(q))
    if not query:
        return None
    if len(query) == 1:
        return _loose_reason(item, query)
    return _phrase_score(item, query)[1]


def _known(value) -> bool:
    return value is not None and value != [] and value != ""


def _match(item: Opportunity, filters: SearchFilters, today: date) -> bool:
    if filters.q and _score(item, filters.q) <= 0:
        return False
    if filters.kind and not _eq(item.kind.value if item.kind else None, filters.kind, filters):
        return False
    if filters.status and not _eq(item.status.value if item.status else None, filters.status, filters):
        return False
    if filters.subsector and not _overlap(item.subsectors, filters.subsector, filters):
        return False
    if filters.programme_id and not _eq(item.programme_id, filters.programme_id, filters):
        return False
    if filters.country and not _country(item, filters.country, filters):
        return False
    if filters.entity_type and not _eq_member(item.eligible_entity_types, filters.entity_type, filters):
        return False
    if filters.consortium_required is not None and not _bool(
        item.consortium_required, filters.consortium_required, filters
    ):
        return False
    if filters.mission_ocean is True and item.mission_ocean is not True:
        return False
    if (filters.amount_min is not None or filters.amount_max is not None) and not _amount(item, filters):
        return False
    if filters.cofunding_min is not None and not _cofunding(item, filters.cofunding_min, filters):
        return False
    if filters.sea_basin and not _overlap(item.sea_basins, filters.sea_basin, filters):
        return False
    if filters.trl is not None and not _trl(item, filters.trl, filters):
        return False
    if filters.closing_within_days is not None:
        if item.deadline_at is None:
            return not filters.exclude_unknown
        horizon = datetime.combine(
            today + timedelta(days=filters.closing_within_days),
            datetime.max.time(),
            tzinfo=item.deadline_at.tzinfo or UTC,
        )
        if item.deadline_at > horizon:
            return False
    return not filters.deadline or deadline_bucket(item, today) in filters.deadline


def deadline_bucket(item: Opportunity, today: date) -> str:
    """Una convocatoria está en un solo grupo: cerrada, se cierra en 60 días, o abierta.

    El grupo se decide por la fecha, no por una etiqueta guardada. Lo que se abre más
    adelante y cierra dentro de esos 60 días cuenta como «se cierra pronto».
    """
    deadline = item.deadline_at.date() if item.deadline_at else None
    if deadline is not None and today <= deadline <= today + timedelta(days=CLOSING_SOON_DAYS):
        return "closing_soon"
    if item.status == OpportunityStatus.closed or (deadline is not None and deadline < today):
        return "closed"
    return "open"


def _eq(value: str | None, wanted: list[str], filters: SearchFilters) -> bool:
    if not _known(value):
        return not filters.exclude_unknown
    return value in wanted


def _overlap(values: list[str], wanted: list[str], filters: SearchFilters) -> bool:
    if not values:
        return not filters.exclude_unknown
    return bool(set(values) & set(wanted))


def _eq_member(values: list[str], wanted: str, filters: SearchFilters) -> bool:
    if not values:
        return not filters.exclude_unknown
    return wanted in values


def _bool(value: bool | None, wanted: bool, filters: SearchFilters) -> bool:
    if value is None:
        return not filters.exclude_unknown
    return value is wanted


def _country(item: Opportunity, countries: list[str], filters: SearchFilters) -> bool:
    """Cualquiera de los países marcados. `uncategorized` son las que no traen país."""
    del filters
    if "uncategorized" in countries and not item.country:
        return True
    return bool(item.country and item.country in countries)


def _amount(item: Opportunity, filters: SearchFilters) -> bool:
    low = item.amount_min_eur
    high = item.amount_max_eur if item.amount_max_eur is not None else item.budget_total_eur
    if low is None and high is None:
        return not filters.exclude_unknown
    if filters.amount_min is not None and high is not None and high < filters.amount_min:
        return False
    return not (filters.amount_max is not None and low is not None and low > filters.amount_max)


def _cofunding(item: Opportunity, minimum: float, filters: SearchFilters) -> bool:
    if item.cofunding_max is None and item.cofunding_min is None:
        return not filters.exclude_unknown
    top = item.cofunding_max if item.cofunding_max is not None else item.cofunding_min
    return top is not None and top >= minimum


def _trl(item: Opportunity, trl: int, filters: SearchFilters) -> bool:
    if item.trl_min is None and item.trl_max is None:
        return not filters.exclude_unknown
    low = item.trl_min or 1
    high = item.trl_max or 9
    return low <= trl <= high


def _facet(items: list[Opportunity], get) -> list[dict]:
    counts: dict[str, int] = {}
    unknown = 0
    for item in items:
        value = get(item)
        if not value:
            unknown += 1
            continue
        counts[value] = counts.get(value, 0) + 1
    return [{"value": key, "count": count, "unknown": unknown} for key, count in sorted(counts.items())]


def _facet_list(items: list[Opportunity], get) -> list[dict]:
    counts: dict[str, int] = {}
    unknown = 0
    for item in items:
        values = get(item) or []
        if not values:
            unknown += 1
            continue
        for value in values:
            counts[value] = counts.get(value, 0) + 1
    return [{"value": key, "count": count, "unknown": unknown} for key, count in sorted(counts.items())]


def _unknown_counts(items: list[Opportunity], filters: SearchFilters) -> dict[str, int]:
    """Cuántas oportunidades no traen el dato de los filtros que el usuario ha puesto."""
    unknown = {}
    if filters.sea_basin:
        unknown["sea_basin"] = sum(1 for item in items if not item.sea_basins)
    if filters.trl is not None:
        unknown["trl"] = sum(1 for item in items if item.trl_min is None and item.trl_max is None)
    if filters.entity_type:
        unknown["entity_type"] = sum(1 for item in items if not item.eligible_entity_types)
    if filters.cofunding_min is not None:
        unknown["cofunding"] = sum(
            1 for item in items if item.cofunding_min is None and item.cofunding_max is None
        )
    return unknown


def suggest_relaxation(items: list[Opportunity], filters: SearchFilters, today: date | None = None) -> str | None:
    """Si la búsqueda queda vacía, dice qué filtro quitaría más resultados."""
    if search_opportunities(items, filters, today)["total"]:
        return None
    best = None
    best_gain = 0
    toggles = [
        ("subsector", "subsector"),
        ("kind", "kind"),
        ("sea_basin", "sea basin"),
        ("programme_id", "programme"),
    ]
    for attr, label in toggles:
        if not getattr(filters, attr):
            continue
        relaxed = SearchFilters(**{**filters.__dict__, attr: []})
        gain = search_opportunities(items, relaxed, today)["total"]
        if gain > best_gain:
            best_gain = gain
            best = label
    if not best:
        return None
    return f"No calls on this heading. {best_gain} match if you drop {best}."
