"""Historial que se enseña en la ficha.

Subvenciones: proyectos de CORDIS. Licitaciones: adjudicaciones de TED. Las dos con umbral.
El texto de cada proyecto se trocea una vez por volcado, no en cada ficha.
"""

import time

from app.models.opportunity import OpportunityKind
from app.partners.score import prepare_corpus, rank_track_record
from app.store import FileStore

_CORDIS = ("cordis-h2020", "cordis-horizon-europe")
_CACHE: dict = {
    "key": None,
    "cordis": None,
    "awards": None,
    "cordis_corpus": None,
    "awards_corpus": None,
}
_SOURCE_LOOKUP = {"client": None, "at": 0.0, "stamp": None}


def clear_track_record_cache() -> None:
    _CACHE.update(key=None, cordis=None, awards=None, cordis_corpus=None, awards_corpus=None)
    _SOURCE_LOOKUP.update(client=None, at=0.0, stamp=None)


def track_record_for(item, store, vertical, *, live: bool = False) -> dict:
    if not live and _stored_is_current(item, store, vertical):
        return _from_saved(store.saved_track_record(item.id))
    record = _from_awards(item, store, vertical) if item.kind == OpportunityKind.tender else _from_cordis(item, store, vertical)
    if not live and _precomputable_status(item):
        store.mark_track_record_pending(item.id)
    return record


def _precomputable_status(item) -> bool:
    from app.models.opportunity import compute_status

    return compute_status(item).value in {"open", "forthcoming"}


def _stored_is_current(item, store, vertical) -> bool:
    if not _precomputable_status(item):
        return False
    saved = store.saved_track_record(item.id)
    if not saved or not saved.get("inputs_hash"):
        return False
    from app.partners.precompute import inputs_hash

    return saved.get("inputs_hash") == inputs_hash(item, store, vertical)


def _from_saved(saved: dict) -> dict:
    return _payload(
        saved.get("status") or "not_loaded",
        saved.get("source") or "cordis",
        items=saved.get("items") or [],
        total=int(saved.get("total") or 0),
        loaded_at=saved.get("loaded_at"),
        since=saved.get("since"),
    )


def _from_cordis(item, store, vertical) -> dict:
    sources = store.track_record_sources()
    loaded = [sources[name] for name in _CORDIS if sources.get(name, {}).get("loaded_at")]
    if not loaded:
        return _payload("not_loaded", "cordis")
    stamp = max(row.get("loaded_at") or "" for row in loaded)
    if _needs_english(item):
        return _payload("not_comparable", "cordis", loaded_at=stamp)
    rows, corpus = _cordis(store)
    ranked, total = rank_track_record(
        item, rows, cfg=vertical.track_record, kind="cordis", corpus=corpus
    )
    return _payload("ok" if ranked else "no_match", "cordis", items=ranked, total=total, loaded_at=stamp)


def _from_awards(item, store, vertical) -> dict:
    sources = store.track_record_sources()
    meta = sources.get("ted-awards") or {}
    rows, corpus = _awards(store)
    if not meta.get("loaded_at") and not rows:
        return _payload("not_loaded", "ted_awards")
    ranked, total = rank_track_record(
        item, rows, cfg=vertical.track_record, kind="awards", corpus=corpus
    )
    return _payload(
        "ok" if ranked else "no_match",
        "ted_awards",
        items=ranked,
        total=total,
        loaded_at=meta.get("loaded_at"),
        since=meta.get("since"),
    )


def _needs_english(item) -> bool:
    """Sin texto en inglés, el parecido con CORDIS mediría el idioma y no el contenido."""
    if item.language in (None, "en"):
        return False
    if item.summary_en:
        return False
    return not (item.title_en and item.title_en != item.title)


def _payload(status: str, source: str, *, items=None, total: int = 0, loaded_at=None, since=None) -> dict:
    rows = items or []
    return {
        "status": status,
        "source": source,
        "total": total,
        "loaded_at": loaded_at,
        "since": since,
        "items": rows,
    }


def _cordis(store) -> tuple[list[dict], object]:
    _refresh(store)
    return _CACHE["cordis"] or [], _CACHE["cordis_corpus"]


def _awards(store) -> tuple[list[dict], object]:
    _refresh(store)
    return _CACHE["awards"] or [], _CACHE["awards_corpus"]


def _refresh(store) -> None:
    key = _cache_key(store)
    if _CACHE["key"] == key and _CACHE["cordis"] is not None:
        return
    cordis = store.cordis_participations()
    awards = [_award_row(item, winner) for item in store.award_notices() for winner in _winners(item)]
    _CACHE["key"] = key
    _CACHE["cordis"] = cordis
    _CACHE["awards"] = awards
    _CACHE["cordis_corpus"] = prepare_corpus(cordis)
    _CACHE["awards_corpus"] = prepare_corpus(awards)


def _cache_key(store):
    if isinstance(store, FileStore):
        return ("file", _mtime(store.partners_path()), _mtime(store.path))
    return ("remote", id(store.client), _remote_stamp(store))


def _remote_stamp(store) -> tuple:
    """Como mucho una lectura de partner_sources cada 60 s. Las tablas grandes, solo si cambia."""
    now = time.monotonic()
    client = id(store.client)
    if (
        _SOURCE_LOOKUP["client"] == client
        and _SOURCE_LOOKUP["stamp"] is not None
        and now - _SOURCE_LOOKUP["at"] < 60
    ):
        return _SOURCE_LOOKUP["stamp"]
    sources = store.track_record_sources()
    stamp = (
        tuple(
            sorted(
                (
                    source_id,
                    row.get("content_hash"),
                    row.get("loaded_at"),
                    row.get("projects"),
                )
                for source_id, row in sources.items()
            )
        ),
        store.award_notice_count(),
    )
    _SOURCE_LOOKUP.update(client=client, at=now, stamp=stamp)
    return stamp


def _mtime(path) -> int:
    return path.stat().st_mtime_ns if path.exists() else 0


def _winners(item) -> list[dict]:
    winners = next((fact.value for fact in item.facts if fact.field == "winners"), None)
    if isinstance(winners, list) and winners:
        return [row for row in winners if isinstance(row, dict) and row.get("name")]
    name = next((fact.value for fact in item.facts if fact.field == "winner_name"), None)
    if name:
        return [{"name": name}]
    return []


def _award_row(item, winner: dict) -> dict:
    size = winner.get("size")
    # TED a veces dice "sme" en vez de "small". No se enseña el código crudo.
    sme = size in {"small", "micro", "sme"}
    return {
        "org_name": winner["name"],
        "country": winner.get("country"),
        "activity_type": None if size in {None, "sme"} else size,
        "pic": winner.get("id_hash"),
        "sme": sme,
        "demo": False,
        "title": _compare_title(item),
        "objective": " ".join(
            part for part in (item.title, item.summary_en or "", item.description or "") if part
        ),
        "url": item.url,
        "role": "winner",
        "end_year": item.published_at.year if item.published_at else None,
        "subsectors": list(item.subsectors),
        "project_id": item.id,
        "cpv": list(item.cpv),
        "call_id": item.call_id,
        "buyer": item.buyer.name if item.buyer else None,
        "amount_eur": next(
            (fact.value for fact in item.facts if fact.field == "award_value_eur"), None
        ),
    }


def _compare_title(item) -> str:
    """Quita solo el país del título inglés de TED y deja la etiqueta CPV, que es lo que casa."""
    title = item.title_en or item.title or ""
    head, separator, rest = title.partition(" – ")
    if separator and rest and len(head.split()) <= 4 and not any(character.isdigit() for character in head):
        return rest
    return title
