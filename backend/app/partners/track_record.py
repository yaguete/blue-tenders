"""Historial que se enseña en la ficha.

Subvenciones: proyectos de CORDIS. Licitaciones: adjudicaciones de TED. Las dos con umbral.
El texto de cada proyecto se trocea una vez por volcado, no en cada ficha.

Quién acaba se guarda con el historial, por proyecto y sin tope, con un trimestre
de margen. La ficha recorta la ventana al abrirse.
"""

import calendar
import time
from datetime import date, timedelta

from app.models.opportunity import OpportunityKind
from app.partners.score import prepare_corpus, track_record_views
from app.store import FileStore

_CORDIS = ("cordis-h2020", "cordis-horizon-europe")
# Margen de la lista guardada: mientras hoy no pase de un trimestre desde el cálculo,
# los candidatos almacenados siguen cubriendo la ventana.
_ENDING_MARGIN_DAYS = 92
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


def ending_soon_for(
    item, store, vertical, *, track: dict | None = None, today: date | None = None, live: bool = False
) -> dict:
    """Consorcios del mismo subsector que terminan dentro de la ventana.

    La fecha es la del registro. Sin fecha no se estima. No mide parecido de texto:
    un proyecto entra por subsector, así que no hace falta que la ficha esté en inglés.
    Un socio es relevante si además sale en el historial de la convocatoria (`track`).

    Los candidatos se guardan por proyecto, sin tope y con un trimestre de margen.
    La ficha recorta la ventana al abrirse. Un registro sin `consortia` (la forma
    anterior, cortada a 30 organizaciones) no vale: se calcula en vivo y queda pendiente.
    """
    window = vertical.track_record.ending_window_months
    today = today or date.today()
    if not live and _precomputable_status(item):
        saved = store.saved_track_record(item.id)
        from app.partners.precompute import inputs_hash

        ending = (saved or {}).get("ending") or {}
        if (
            saved
            and ending.get("consortia") is not None
            and saved.get("inputs_hash") == inputs_hash(item, store, vertical)
            and _ending_fresh(saved, today)
        ):
            return _ending_view(ending, today, window)
        store.mark_track_record_pending(item.id)
    stored = _ending_collect(item, store, today, window, track)
    if live:
        return stored
    return _ending_view(stored, today, window)


def _relevant_keys(track: dict | None) -> set[str]:
    """Los socios de los proyectos parecidos que enseña la ficha. Clave: pic, o el nombre.

    Un registro anterior sin `projects` usa la lista por organización.
    """
    if not track or track.get("status") != "ok":
        return set()
    if track.get("projects") is not None:
        return {
            partner.get("pic") or partner.get("org_name")
            for project in track["projects"]
            for partner in project.get("partners") or []
        }
    return {org.get("pic") or org.get("org_name") for org in track.get("items") or []}


def _ending_collect(item, store, today: date, window: int, track: dict | None = None) -> dict:
    """Consorcios que terminan entre hoy y la ventana más un trimestre de margen."""
    sources = store.track_record_sources()
    loaded = [sources[name] for name in _CORDIS if sources.get(name, {}).get("loaded_at")]
    if not loaded:
        return _ending_payload("not_loaded", window)
    stamp = max(row.get("loaded_at") or "" for row in loaded)
    horizon = _add_months(today, window) + timedelta(days=_ENDING_MARGIN_DAYS)
    wanted = set(item.subsectors or [])
    relevant = _relevant_keys(track)
    rows, _corpus = _cordis(store)
    seen = set()
    by_project: dict[str, dict] = {}
    for row in rows:
        end = _as_date(row.get("end_date"))
        if end is None or end < today or end > horizon:
            continue
        if not wanted.intersection(row.get("subsectors") or []):
            continue
        org_key = row.get("pic") or row.get("org_name")
        project_id = row.get("project_id") or row.get("url") or row.get("acronym")
        pair = (org_key, project_id)
        if not project_id or pair in seen:
            continue
        seen.add(pair)
        bucket = by_project.setdefault(
            project_id,
            {
                "id": project_id,
                "acronym": row.get("acronym"),
                "title": row.get("title"),
                "url": row.get("url"),
                "programme_id": row.get("programme_id"),
                "end_date": end.isoformat(),
                "partners": [],
            },
        )
        bucket["partners"].append(
            {
                "org_name": row.get("org_name"),
                "country": row.get("country"),
                "activity_type": row.get("activity_type"),
                "pic": row.get("pic"),
                "sme": row.get("sme"),
                "demo": bool(row.get("demo")),
                "role": row.get("role"),
                "relevant": org_key in relevant,
            }
        )
    consortia = sorted(by_project.values(), key=lambda consortium: (consortium["end_date"], consortium.get("title") or ""))
    pairs = [
        [partner.get("pic") or partner.get("org_name"), consortium["end_date"]]
        for consortium in consortia
        for partner in consortium["partners"]
        if partner["relevant"]
    ]
    return _ending_stored("ok" if consortia else "no_match", window, consortia, pairs, track, stamp)


def _ending_view(stored: dict, today: date, window: int) -> dict:
    """Recorta los consorcios guardados a la ventana de hoy. `relevant` no sale."""
    if stored.get("status") == "not_loaded":
        return _ending_payload("not_loaded", window)
    horizon = _add_months(today, window).isoformat()
    floor = today.isoformat()
    consortia = [
        consortium
        for consortium in stored.get("consortia") or []
        if floor <= str(consortium.get("end_date") or "") <= horizon
    ]
    consortia.sort(key=lambda consortium: (consortium.get("end_date") or "", consortium.get("title") or ""))
    return _ending_payload(
        "ok" if consortia else "no_match",
        window,
        consortia=consortia,
        total=_org_count(consortia),
        consortia_total=len(consortia),
        relevant_total=_relevant_count(consortia) if stored.get("track_ok") else None,
        loaded_at=stored.get("loaded_at"),
    )


def wrapping_up_counts(rows: dict[str, dict], today: date, window: int) -> dict[str, int]:
    """Organizaciones relevantes distintas que acaban dentro de la ventana, por convocatoria.

    `rows` es lo que devuelve `ending_relevance`: computed_at y la lista `relevant`.
    Sin esa lista, o con el registro caducado, la convocatoria no entra. No se estima.
    """
    horizon = _add_months(today, window).isoformat()
    floor = today.isoformat()
    counts: dict[str, int] = {}
    for opportunity_id, row in rows.items():
        if not _ending_fresh(row, today):
            continue
        orgs = {
            pair[0]
            for pair in row.get("relevant") or []
            if isinstance(pair, (list, tuple)) and len(pair) >= 2 and floor <= str(pair[1] or "") <= horizon
        }
        if orgs:
            counts[opportunity_id] = len(orgs)
    return counts


def _org_count(consortia: list[dict]) -> int:
    return len({partner.get("pic") or partner.get("org_name") for consortium in consortia for partner in consortium.get("partners") or []})


def _relevant_count(consortia: list[dict]) -> int:
    return len(
        {
            partner.get("pic") or partner.get("org_name")
            for consortium in consortia
            for partner in consortium.get("partners") or []
            if partner.get("relevant")
        }
    )


def _ending_stored(status: str, window: int, consortia: list[dict], pairs: list, track, loaded_at) -> dict:
    track_ok = bool(track) and track.get("status") == "ok"
    body = _ending_payload(
        status,
        window,
        consortia=consortia,
        total=_org_count(consortia),
        consortia_total=len(consortia),
        relevant_total=_relevant_count(consortia) if track_ok else None,
        loaded_at=loaded_at,
    )
    body["relevant"] = pairs
    body["track_ok"] = track_ok
    return body


def _ending_fresh(saved: dict, today: date) -> bool:
    computed = _as_date(str(saved.get("computed_at") or "")[:10])
    return computed is not None and (today - computed).days <= _ENDING_MARGIN_DAYS


def _precomputable_status(item) -> bool:
    from app.models.opportunity import compute_status

    return compute_status(item).value in {"open", "forthcoming"}


def _stored_is_current(item, store, vertical) -> bool:
    if not _precomputable_status(item):
        return False
    saved = store.saved_track_record(item.id)
    if not saved or not saved.get("inputs_hash"):
        return False
    # Un historial guardado antes de agrupar por proyecto (o por adjudicación) no vale: la ficha
    # lo enseña agrupado, y la lista por organización viene cortada en 30.
    if saved.get("status") == "ok" and saved.get("projects") is None:
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
        projects=saved.get("projects"),
        projects_total=saved.get("projects_total"),
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
    views = track_record_views(item, rows, cfg=vertical.track_record, kind="cordis", corpus=corpus)
    return _payload(
        "ok" if views["items"] else "no_match",
        "cordis",
        items=views["items"],
        total=views["total"],
        loaded_at=stamp,
        projects=views["projects"],
        projects_total=views["projects_total"],
    )


def _from_awards(item, store, vertical) -> dict:
    sources = store.track_record_sources()
    meta = sources.get("ted-awards") or {}
    rows, corpus = _awards(store)
    if not meta.get("loaded_at") and not rows:
        return _payload("not_loaded", "ted_awards")
    views = track_record_views(item, rows, cfg=vertical.track_record, kind="awards", corpus=corpus)
    return _payload(
        "ok" if views["items"] else "no_match",
        "ted_awards",
        items=views["items"],
        total=views["total"],
        loaded_at=meta.get("loaded_at"),
        since=meta.get("since"),
        projects=views["projects"],
        projects_total=views["projects_total"],
    )


def _needs_english(item) -> bool:
    """Sin texto en inglés, el parecido con CORDIS mediría el idioma y no el contenido."""
    if item.language in (None, "en"):
        return False
    if item.summary_en:
        return False
    return not (item.title_en and item.title_en != item.title)


def _ending_payload(
    status: str,
    window: int,
    *,
    consortia=None,
    total: int = 0,
    consortia_total: int = 0,
    relevant_total: int | None = None,
    loaded_at=None,
) -> dict:
    return {
        "status": status,
        "source": "cordis",
        "window_months": window,
        "total": total,
        "consortia_total": consortia_total,
        "relevant_total": relevant_total,
        "loaded_at": loaded_at,
        "consortia": consortia or [],
    }


def _add_months(day: date, months: int) -> date:
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _as_date(value) -> date | None:
    text = str(value or "")[:10]
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _payload(
    status: str,
    source: str,
    *,
    items=None,
    total: int = 0,
    loaded_at=None,
    since=None,
    projects=None,
    projects_total=None,
) -> dict:
    """`items` va por organización: lo usa el espejo normalizado. `projects`, por proyecto
    parecido (o adjudicación) con todos sus socios: lo que enseña la ficha."""
    rows = items or []
    if projects is None and status != "ok":
        projects, projects_total = [], 0
    return {
        "status": status,
        "source": source,
        "total": total,
        "loaded_at": loaded_at,
        "since": since,
        "items": rows,
        "projects": projects,
        "projects_total": projects_total,
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
    notices = store.award_notices()
    # Solo los expedientes de esas adjudicaciones: la tabla de convocatorias no se recorre entera.
    bases = store.call_budgets({item.call_id for item in notices})
    awards = [_award_row(item, winner, bases) for item in notices for winner in _winners(item)]
    _CACHE["key"] = key
    _CACHE["cordis"] = cordis
    _CACHE["awards"] = awards
    _CACHE["cordis_corpus"] = prepare_corpus(cordis)
    _CACHE["awards_corpus"] = prepare_corpus(awards)


def _cache_key(store):
    if isinstance(store, FileStore):
        return ("file", _mtime(store.partners_path()), _mtime(store.path))
    return ("remote", _cache_token(store), _remote_stamp(store))


def _cache_token(store) -> str:
    """La API crea un store por petición: el token compartido hace que el caché aguante.

    Con un cliente inyectado (los tests) vale el id, que es lo que hacía antes.
    """
    return getattr(store, "_cache_token", None) or id(store.client)


def _remote_stamp(store) -> tuple:
    """Como mucho una lectura de partner_sources cada 60 s. Las tablas grandes, solo si cambia."""
    now = time.monotonic()
    client = _cache_token(store)
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


def _award_row(item, winner: dict, bases: dict[str, float]) -> dict:
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
        "base_amount_eur": bases.get(item.call_id) if item.call_id else None,
        "contract_end": next(
            (fact.value for fact in item.facts if fact.field == "contract_end_at"), None
        ),
    }


def _compare_title(item) -> str:
    """Quita solo el país del título inglés de TED y deja la etiqueta CPV, que es lo que casa."""
    title = item.title_en or item.title or ""
    head, separator, rest = title.partition(" – ")
    if separator and rest and len(head.split()) <= 4 and not any(character.isdigit() for character in head):
        return rest
    return title
