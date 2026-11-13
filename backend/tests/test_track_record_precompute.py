"""El historial guardado se invalida solo por la entrada que cambió, y no se enseña viejo."""

from datetime import UTC, datetime

from app.api.opportunities import detail
from app.models.opportunity import Opportunity, OpportunityKind, OpportunityType
from app.partners.precompute import compute_and_save, inputs_hash, refresh_pending, refresh_source
from app.store import FileStore, SupabaseStore
from app.vertical import load_vertical
from tests.fake_supabase import FakeSupabase


def _open(name: str, *, kind: str = "grant") -> Opportunity:
    common = {
        "id": name,
        "source_id": "eu-ft" if kind == "grant" else "ted",
        "external_id": name,
        "url": "https://example.test/" + name,
        "title": name,
        "title_en": name,
        "deadline_at": datetime(2026, 12, 20, tzinfo=UTC),
        "language": "en",
    }
    if kind == "tender":
        common["type"] = OpportunityType.tender
        common["kind"] = OpportunityKind.tender
    else:
        common["type"] = OpportunityType.grant
        common["kind"] = OpportunityKind.grant
    return Opportunity(**common)


def _loaded(store: FileStore) -> None:
    store.save_track_record_source(
        "cordis-h2020", content_hash="dump-1", loaded_at="2026-11-11T00:00:00+00:00", projects=0
    )


def test_only_the_changed_call_is_recomputed(tmp_path):
    store = FileStore(tmp_path / "opportunities.json")
    _loaded(store)
    first, second = _open("one"), _open("two")
    store.upsert_opportunities([first, second])
    vertical = load_vertical()
    compute_and_save(first, store, vertical)
    compute_and_save(second, store, vertical)
    kept = store.saved_track_record("two")["inputs_hash"]
    changed = _open("one")
    changed = Opportunity(**{**changed.model_dump(), "title": "one rewritten", "content_hash": None})
    store.upsert_opportunities([changed])
    changed = store.get("one")
    compute_and_save(changed, store, vertical)
    assert store.saved_track_record("two")["inputs_hash"] == kept
    assert store.saved_track_record("one")["inputs_hash"] != kept


def test_a_new_dump_recomputes_grants_and_leaves_tenders(tmp_path):
    store = FileStore(tmp_path / "opportunities.json")
    _loaded(store)
    store.save_track_record_source("ted-awards", content_hash="awards-1", loaded_at="2026-11-11", projects=1)
    grant, tender = _open("grant-call"), _open("tender-call", kind="tender")
    store.upsert_opportunities([grant, tender])
    vertical = load_vertical()
    compute_and_save(grant, store, vertical)
    compute_and_save(tender, store, vertical)
    tender_hash = store.saved_track_record("tender-call")["inputs_hash"]
    store.save_track_record_source("cordis-h2020", content_hash="dump-2", loaded_at="2026-11-12", projects=1)
    refresh_source("cordis", store, vertical)
    assert store.saved_track_record("grant-call")["inputs_hash"] == inputs_hash(store.get("grant-call"), store, vertical)
    assert store.saved_track_record("tender-call")["inputs_hash"] == tender_hash


def test_a_yaml_change_recomputes_every_open_call(tmp_path, monkeypatch):
    store = FileStore(tmp_path / "opportunities.json")
    _loaded(store)
    store.upsert_opportunities([_open("only")])
    vertical = load_vertical()
    compute_and_save(store.get("only"), store, vertical)
    store.set_track_record_config_hash("previous")
    before = store.saved_track_record("only")["computed_at"]
    monkeypatch.setattr(
        "app.partners.precompute.config_hash",
        lambda _vertical: "changed",
    )
    refresh_pending(store, vertical)
    assert store.saved_track_record("only")["computed_at"] != before
    assert store.track_record_config_hash() == "changed"


def test_a_stale_record_is_not_shown(tmp_path):
    store = FileStore(tmp_path / "opportunities.json")
    _loaded(store)
    store.upsert_opportunities([_open("live-call")])
    store.save_track_record(
        "live-call",
        {
            "source": "cordis",
            "status": "ok",
            "total": 1,
            "inputs_hash": "outdated",
            "items": [{"org_name": "OLD LAB", "pic": "1", "score": 1, "projects": []}],
        },
    )
    shown = __import__("app.partners.track_record", fromlist=["track_record_for"]).track_record_for(
        store.get("live-call"), store, load_vertical()
    )
    assert [org["org_name"] for org in shown["items"]] != ["OLD LAB"]
    assert "live-call" in store.pending_track_records()


def test_detail_reads_the_saved_record_from_supabase(monkeypatch):
    store = SupabaseStore(client=FakeSupabase())
    item = _open("saved-call")
    store.client.table("opportunities").upsert([item.model_dump(mode="json")]).execute()
    _loaded_supabase(store)
    vertical = load_vertical()
    current = inputs_hash(item, store, vertical)
    store.save_track_record(
        item.id,
        {
            "source": "cordis",
            "status": "ok",
            "total": 1,
            "inputs_hash": current,
            "loaded_at": "2026-11-11T00:00:00+00:00",
            "items": [{"org_name": "Saved Lab", "pic": "9", "score": 1, "projects": []}],
        },
    )
    monkeypatch.setattr("app.api.opportunities.get_store", lambda: store)
    body = detail(item.id)
    assert body["track_record"]["items"][0]["org_name"] == "Saved Lab"
    rewritten = Opportunity(**{**item.model_dump(), "title": "saved-call rewritten", "content_hash": None})
    store.client.table("opportunities").upsert([rewritten.model_dump(mode="json")]).execute()
    body = detail(item.id)
    assert [org["org_name"] for org in body["track_record"]["items"]] != ["Saved Lab"]


def _loaded_supabase(store: SupabaseStore) -> None:
    store.save_track_record_source(
        "cordis-h2020", content_hash="dump-1", loaded_at="2026-11-11T00:00:00+00:00", projects=0
    )
