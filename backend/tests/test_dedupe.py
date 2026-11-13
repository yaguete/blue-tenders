from datetime import UTC, datetime

from app.models.opportunity import Opportunity
from app.pipeline.run import dedupe
from app.store import FileStore


def _call(source: str, external: str, key: str) -> Opportunity:
    return Opportunity(
        id=Opportunity.make_id(source, external),
        source_id=source,
        external_id=external,
        url=f"https://example.test/{source}/{external}",
        title="Submarine cable",
        dedupe_key=key,
        deadline_at=datetime(2026, 12, 1, tzinfo=UTC),
        raw={"procedure-identifier": key},
    )


def test_a_later_ted_notice_hides_the_placsp_copy_already_stored(tmp_path):
    store = FileStore(tmp_path / "opportunities.json")
    placsp = _call("placsp", "EXP-1", "EXP-1")
    store.upsert_opportunities([placsp])
    ted = _call("ted", "1-2026", "EXP-1")
    kept = dedupe([ted], store)
    ids = {item.id: item.listed for item in kept}
    assert ids[ted.id] is True
    assert ids[placsp.id] is False
    store.upsert_opportunities(kept)
    saved = {item.id: item.listed for item in store.opportunities()}
    assert saved[ted.id] is True
    assert saved[placsp.id] is False


def test_an_invalid_call_is_queued_for_review(tmp_path):
    from app.pipeline.run import enrich
    from app.vertical import load_vertical

    store = FileStore(tmp_path / "opportunities.json")
    # enrich lee el almacén por defecto; este test solo mira la cola que deja en la ficha.
    item = Opportunity(
        id="bad",
        source_id="curated",
        external_id="bad",
        url="https://example.test/bad",
        title="Offshore wind grant",
        title_en="Offshore wind grant",
        description="Offshore wind.",
        language="en",
        cofunding_min=140,
        deadline_at=datetime(2026, 12, 1, tzinfo=UTC),
    )
    enriched = enrich([item], load_vertical())
    assert enriched
    assert enriched[0].review_items
    assert enriched[0].review_items[0]["reason"] == "invalid"
    store.add_reviews(enriched[0].review_items)
    store.add_reviews(enriched[0].review_items)
    assert len(store.load()["reviews"]) == 1


def test_without_a_shared_key_both_notices_stay(tmp_path):
    store = FileStore(tmp_path / "opportunities.json")
    placsp = _call("placsp", "EXP-9", "EXP-9")
    store.upsert_opportunities([placsp])
    ted = _call("ted", "2-2026", "OTHER")
    kept = dedupe([ted], store)
    assert [item.id for item in kept] == [ted.id]
