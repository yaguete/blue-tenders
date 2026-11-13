"""La caché del historial no cambia el resultado y no vuelve a trocear los proyectos."""

import math

from app.partners.score import (
    _doc_key,
    prepare_corpus,
    project_token_calls,
    rank_track_record,
    reset_project_token_calls,
    score_project,
)
from app.partners.track_record import clear_track_record_cache, track_record_for
from app.settings import settings
from app.store import FileStore
from app.vertical import load_vertical

_FICHES = (
    "89cf5485ea18eea9",
    "b1fbad7b4f2cf815",
    "da73acc800f2d66d",
    "923148b16e92f831",
    "0f1832f78375d045",
)


def _signature(record: dict) -> tuple:
    orgs = []
    for org in record["items"]:
        projects = tuple((project["id"], project["evidence"], project["score"]) for project in org["projects"])
        orgs.append((org.get("pic"), org["org_name"], org["score"], projects))
    return (record["status"], record["total"], tuple(orgs))


def test_prepared_scores_match_tokenizing_each_row():
    store = FileStore(settings.data_dir / "opportunities.json")
    rows = store.cordis_participations()
    item = store.get("89cf5485ea18eea9")
    if not rows or item is None:
        return
    corpus = prepare_corpus(rows)
    seen = set()
    checked = 0
    for row in rows:
        key = _doc_key(row)
        if key in seen:
            continue
        seen.add(key)
        naive = score_project(item, row, idf=corpus.idf, idf_default=corpus.default)
        cached = score_project(
            item,
            row,
            idf=corpus.idf,
            idf_default=corpus.default,
            proj_stats=corpus.projects[key],
        )
        assert cached["score"] == naive["score"]
        assert math.isclose(cached["parts"]["text"], naive["parts"]["text"], rel_tol=0, abs_tol=1e-12)
        assert cached["parts"]["shared_tokens"] == naive["parts"]["shared_tokens"]
        assert cached["parts"]["same_topic"] == naive["parts"]["same_topic"]
        checked += 1
        if checked == 40:
            break
    assert checked == 40


def test_the_five_fiches_keep_the_same_organisations():
    store = FileStore(settings.data_dir / "opportunities.json")
    vertical = load_vertical()
    clear_track_record_cache()
    for opportunity_id in _FICHES:
        item = store.get(opportunity_id)
        if item is None:
            continue
        live = track_record_for(item, store, vertical)
        if live["source"] == "cordis":
            rows = store.cordis_participations()
            kind = "cordis"
        else:
            from app.partners.track_record import _awards

            rows, _corpus = _awards(store)
            kind = "awards"
        fresh_items, fresh_total = rank_track_record(item, rows, cfg=vertical.track_record, kind=kind)
        if live["status"] in {"ok", "no_match"}:
            assert _signature(live) == _signature(
                {"status": "ok" if fresh_items else "no_match", "total": fresh_total, "items": fresh_items}
            )


def test_the_second_call_does_not_tokenize_projects_again():
    store = FileStore(settings.data_dir / "opportunities.json")
    item = store.get("89cf5485ea18eea9")
    if item is None or not store.cordis_participations():
        return
    clear_track_record_cache()
    reset_project_token_calls()
    track_record_for(item, store, load_vertical())
    after_first = project_token_calls()
    assert after_first > 0
    track_record_for(item, store, load_vertical())
    assert project_token_calls() == after_first
