"""Historial calculado una vez por convocatoria, mientras no cambien sus entradas.

Las entradas son el texto de la convocatoria, el volcado y la configuración del YAML.
Las cerradas no se precalculan: su ficha se calcula al abrirla.
"""

import hashlib
import json
from datetime import UTC, date, datetime

from app.models.opportunity import OpportunityKind, compute_status
from app.partners.cordis import criteria_hash
from app.partners.track_record import track_record_for

_CORDIS = ("cordis-h2020", "cordis-horizon-europe")


def config_hash(vertical) -> str:
    payload = {
        "criteria": criteria_hash(vertical),
        "track_record": vertical.track_record.model_dump(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def inputs_hash(item, store, vertical) -> str:
    sources = store.track_record_sources()
    if item.kind == OpportunityKind.tender:
        dump = sources.get("ted-awards") or {}
        dump_part = "|".join(str(dump.get(key) or "") for key in ("content_hash", "loaded_at", "projects"))
    else:
        dump_part = "|".join(
            f"{name}:{(sources.get(name) or {}).get('content_hash')}:{(sources.get(name) or {}).get('loaded_at')}"
            for name in _CORDIS
        )
    raw = "\n".join([item.content_hash or "", dump_part, config_hash(vertical)])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def precomputable(item, today: date | None = None) -> bool:
    if item is None or not item.searchable():
        return False
    return compute_status(item, today).value in {"open", "forthcoming"}


def compute_and_save(item, store, vertical) -> dict:
    record = track_record_for(item, store, vertical, live=True)
    if item.kind != OpportunityKind.tender:
        from app.partners.track_record import ending_soon_for

        # Candidatos con margen: la ficha recorta la ventana al abrirse.
        # `track` marca qué socios del consorcio salen también en el historial.
        record["ending"] = ending_soon_for(item, store, vertical, track=record, live=True)
    record["inputs_hash"] = inputs_hash(item, store, vertical)
    record["computed_at"] = datetime.now(UTC).isoformat()
    record["pending"] = False
    store.save_track_record(item.id, record)
    return record


def refresh_opportunities(items, store=None, vertical=None) -> int:
    """Recalcula solo estas convocatorias, si siguen abiertas o próximas."""
    from app.store import get_store
    from app.vertical import load_vertical

    store = store or get_store()
    vertical = vertical or load_vertical()
    done = 0
    for item in items:
        if precomputable(item):
            compute_and_save(item, store, vertical)
            done += 1
    return done


def refresh_source(source: str, store=None, vertical=None) -> int:
    """Recalcula las convocatorias abiertas de un origen: cordis o ted_awards."""
    from app.store import get_store
    from app.vertical import load_vertical

    store = store or get_store()
    vertical = vertical or load_vertical()
    want_tender = source == "ted_awards"
    chosen = [
        item
        for item in store.opportunities()
        if precomputable(item) and ((item.kind == OpportunityKind.tender) == want_tender)
    ]
    return refresh_opportunities(chosen, store, vertical)


def refresh_pending(store=None, vertical=None, *, everything: bool = False) -> int:
    from app.store import get_store
    from app.vertical import load_vertical

    store = store or get_store()
    vertical = vertical or load_vertical()
    current = config_hash(vertical)
    if everything or store.track_record_config_hash() != current:
        store.set_track_record_config_hash(current)
        chosen = [item for item in store.opportunities() if precomputable(item)]
        return refresh_opportunities(chosen, store, vertical)
    by_id = {item.id: item for item in store.opportunities()}
    chosen = [by_id[item_id] for item_id in store.pending_track_records() if item_id in by_id]
    return refresh_opportunities(chosen, store, vertical)
