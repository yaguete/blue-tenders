"""ingest → normalize → dedupe → enrich → index."""

from datetime import date

# Los nombres con guion bajo se conservan: `app.enrich.classify` los importa de aquí.
from app.keywords import keyword_words as _keyword_words
from app.keywords import mentions as _mentions
from app.keywords import tokens as _tokens
from app.models.tender import Tender
from app.sources import REGISTRY
from app.sources.base import source_subsectors
from app.vertical import Vertical


def ingest(source_id: str, since: date, vertical: Vertical) -> list[Tender]:
    src = REGISTRY[source_id]
    out = []
    for raw in src.fetch(since, vertical):
        try:
            out.append(src.to_opportunity(raw))
        except Exception as e:  # noqa: BLE001  una fuente rota no tumba la ingesta
            print(f"[{source_id}] skip: {e}")
    return out


def prefilter(tenders: list[Tender], vertical: Vertical) -> list[Tender]:
    """Filtro barato por keywords antes de gastar LLM.

    Solo ahorra, no decide: está pensado para no perder nada relevante. Por eso busca
    palabras completas (no subcadenas) y no aplica `exclude_keywords`: descartar un texto
    porque menciona "onshore" tira convocatorias de eólica "offshore and onshore". Las
    exclusiones son ejemplos negativos para el clasificador de `enrich`.

    Aquí solo se ven el título y la descripción. Si la fuente ya encontró el vocabulario del
    vertical en el texto completo del registro (`source_subsectors`), el registro pasa.
    """
    keywords = [_keyword_words(k) for s in vertical.active_subsectors for k in s.keywords]
    kept = []
    for t in tenders:
        if source_subsectors(t.raw):
            kept.append(t)
            continue
        tokens = _tokens(f"{t.title} | {t.title_en or ''} | {t.description or ''}")
        if any(_mentions(tokens, k) for k in keywords):
            kept.append(t)
    return kept


def dedupe(tenders: list[Tender]) -> list[Tender]:
    """Por id de fuente y, entre TED y PLACSP, por expediente si los dos lo traen.

    Una licitación y su adjudicación son el mismo expediente y las dos se quedan: si no,
    «Who won» no tiene con qué cruzar. Solo se descarta el duplicado entre fuentes distintas.
    """
    by_id: dict[str, Tender] = {}
    for tender in tenders:
        by_id[tender.id] = tender
    seen_procedure: dict[str, str] = {}
    dropped = set()
    for tender in by_id.values():
        procedure = str((tender.raw or {}).get("procedure-identifier") or "")
        if not procedure:
            continue
        key = procedure.strip().lower()
        previous_id = seen_procedure.get(key)
        if not previous_id or previous_id == tender.id:
            seen_procedure[key] = tender.id
            continue
        previous = by_id[previous_id]
        if previous.source_id == tender.source_id:
            if previous.notice == tender.notice:
                dropped.add(previous_id)
                seen_procedure[key] = tender.id
            continue
        # Se queda el de TED si uno de los dos lo es: el anuncio europeo es el canónico.
        keep_ted = previous.source_id == "ted" or tender.source_id != "ted"
        dropped.add(tender.id if keep_ted else previous_id)
        if not keep_ted:
            seen_procedure[key] = tender.id
    return [tender for tender in by_id.values() if tender.id not in dropped]


def enrich(tenders: list[Tender], vertical: Vertical) -> list[Tender]:
    """Reglas siempre. LLM solo dentro de classify/analyse/translate si hay clave."""
    from app.enrich.analyse import analyse
    from app.enrich.classify import classify, classify_rules
    from app.enrich.documents import fetch_documents
    from app.enrich.rules import apply_programme_rules, apply_sea_basins
    from app.enrich.translate import translate
    from app.models.opportunity import NoticeKind
    from app.quality.validate import validate_opportunity

    known = {}
    try:
        from app.store import get_store

        known = get_store().content_hashes([tender.id for tender in tenders])
    except Exception as exc:  # noqa: BLE001  sin almacén se enriquece todo
        print(f"[enrich] sin hashes previos: {exc}")
    kept = []
    for tender in tenders:
        if known.get(tender.id) == tender.content_hash:
            continue
        if tender.notice == NoticeKind.award_notice:
            # Una adjudicación no tiene ficha: clasificar por reglas y no gastar el modelo.
            classify_rules(tender, vertical)
            if not tender.subsectors and tender.source_id != "curated":
                continue
            tender.content_hash = tender.compute_hash()
            kept.append(tender)
            continue
        before = tender.content_hash
        classify(tender, vertical)
        if not tender.subsectors and tender.source_id != "curated":
            continue
        apply_programme_rules(tender)
        apply_sea_basins(tender)
        translate(tender)
        analyse(tender)
        tender.content_hash = tender.compute_hash()
        errors = validate_opportunity(tender)
        if errors:
            tender.review_status = "invalid:" + "; ".join(errors)
        elif before != tender.content_hash:
            tender.review_status = tender.review_status or "changed"
        fetch_documents(tender)
        kept.append(tender)
    return kept


def index(tenders: list[Tender]) -> int:
    from app.partners.precompute import refresh_opportunities
    from app.store import get_store

    store = get_store()
    saved = store.upsert_opportunities(tenders)
    refresh_opportunities(tenders, store)
    return saved
