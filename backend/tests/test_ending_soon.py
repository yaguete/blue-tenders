"""Proyectos que terminan en la ventana. La fecha es la del registro, no una estimación.

Los proyectos CORDIS con status TERMINATED no llegan al almacén: lo cubre test_cordis.
"""

from datetime import UTC, date, datetime

from app.api.opportunities import detail
from app.models.opportunity import Opportunity, OpportunityKind, OpportunityType
from app.partners.track_record import clear_track_record_cache, ending_soon_for
from app.store import FileStore
from app.vertical import load_vertical

TODAY = date(2026, 11, 13)


def _grant(**kwargs) -> Opportunity:
    base = {
        "id": "call",
        "source_id": "eu-ft",
        "external_id": "HORIZON-CL5-2023-D3-02-15",
        "url": "https://ec.europa.eu/call",
        "title": "Offshore wind",
        "type": OpportunityType.grant,
        "kind": OpportunityKind.grant,
        "subsectors": ["offshore-wind"],
        "language": "es",
    }
    base.update(kwargs)
    return Opportunity(**base)


def _project(project_id: str, end_date: str | None, **kwargs) -> dict:
    row = {
        "id": project_id,
        "source": "cordis-h2020",
        "programme_id": "h2020",
        "acronym": "WIND",
        "title": "Offshore wind blades",
        "subsectors": ["offshore-wind"],
        "url": f"https://cordis.europa.eu/project/id/{project_id}",
        "end_date": end_date,
    }
    row.update(kwargs)
    return row


def _load(store: FileStore, projects: list[dict], *, source_id: str = "cordis-h2020") -> None:
    orgs = [{"id": "111", "pic": "111", "name": "Wind Lab", "country": "ES", "activity_type": "REC", "sme": False}]
    parts = [{"org_id": "111", "project_id": project["id"], "role": "coordinator"} for project in projects]
    for project in projects:
        project["source"] = source_id
    store.replace_cordis(
        source_id,
        orgs,
        projects,
        parts,
        {"loaded_at": "2026-11-11T00:00:00+00:00", "projects": len(projects)},
    )


def test_without_a_dump_the_window_is_not_loaded(tmp_path):
    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    body = ending_soon_for(_grant(), store, load_vertical(), today=TODAY)
    assert body["status"] == "not_loaded"
    assert body["window_months"] == 9
    assert body["items"] == []


def test_only_a_registered_end_date_inside_the_window_is_kept(tmp_path):
    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    inside = _project("h2020:1", "2027-05-01")
    later = _project("h2020:2", "2027-11-30", acronym="LATER")
    past = _project("h2020:3", "2026-06-01", acronym="PAST")
    edge = _project("h2020:4", "2027-08-13", acronym="EDGE")
    today = _project("h2020:5", TODAY.isoformat(), acronym="TODAY")
    _load(store, [inside, later, past, edge, today])
    body = ending_soon_for(_grant(), store, load_vertical(), today=TODAY)
    acronyms = [project["acronym"] for org in body["items"] for project in org["projects"]]
    assert body["status"] == "ok"
    assert acronyms == ["TODAY", "WIND", "EDGE"]
    assert body["items"][0]["projects"][0]["end_date"] == "2026-11-13"
    assert body["items"][0]["org_name"] == "Wind Lab"


def test_a_missing_date_is_not_guessed_from_the_year(tmp_path):
    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    _load(store, [_project("h2020:9", None, end_year=2027)])
    body = ending_soon_for(_grant(), store, load_vertical(), today=TODAY)
    assert body["status"] == "no_match"
    assert body["items"] == []


def test_another_subsector_stays_out(tmp_path):
    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    _load(store, [_project("h2020:1", "2027-05-01", subsectors=["ocean-energy"])])
    body = ending_soon_for(_grant(), store, load_vertical(), today=TODAY)
    assert body["status"] == "no_match"


def test_a_life_row_in_the_dump_uses_the_same_window(tmp_path):
    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    store.save_track_record_source("cordis-h2020", loaded_at="2026-11-11T00:00:00+00:00", projects=0)
    life = _project(
        "life:1",
        "2027-04-30",
        programme_id="life",
        acronym="LIFEWIND",
        url="https://webgate.ec.europa.eu/life/publicWebsite/project/life-1",
    )
    _load(store, [life], source_id="life")
    body = ending_soon_for(_grant(), store, load_vertical(), today=TODAY)
    assert body["items"][0]["projects"][0]["programme_id"] == "life"
    assert body["items"][0]["projects"][0]["end_date"] == "2027-04-30"


def test_detail_sends_the_window_on_a_grant_and_not_on_a_tender(tmp_path, monkeypatch):
    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    grant = _grant(id="grant-call")
    tender = Opportunity(
        id="tender-call",
        source_id="ted",
        external_id="1",
        url="https://ted.europa.eu/1",
        title="Cable",
        type=OpportunityType.tender,
        kind=OpportunityKind.tender,
        subsectors=["offshore-wind"],
    )
    store.upsert_opportunities([grant, tender])
    _load(store, [_project("h2020:1", "2027-05-01")])
    monkeypatch.setattr("app.api.opportunities.get_store", lambda: store)
    grant_body = detail("grant-call")
    assert grant_body["ending_soon"]["status"] == "ok"
    assert grant_body["ending_soon"]["window_months"] == 9
    assert grant_body["ending_soon"]["items"][0]["projects"][0]["end_date"] == "2027-05-01"
    assert "ending_soon" not in detail("tender-call")


def test_a_saved_ending_is_trimmed_to_the_window_without_pulling_the_dump(tmp_path):
    from app.partners.precompute import compute_and_save

    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    # Con plazo: abierta, y por tanto con registro precalculado.
    grant = _grant(id="warm-call", deadline_at=datetime(2027, 1, 31, tzinfo=UTC))
    store.upsert_opportunities([grant])
    _load(store, [_project("h2020:1", "2027-05-01"), _project("h2020:2", "2027-10-01", acronym="MARGIN")])
    compute_and_save(grant, store, load_vertical())
    saved = store.saved_track_record("warm-call")
    assert saved["ending"]["status"] == "ok"
    stored = [p["acronym"] for org in saved["ending"]["items"] for p in org["projects"]]
    assert stored == ["WIND", "MARGIN"]  # el margen de un trimestre se guarda, la ventana no
    clear_track_record_cache()
    body = ending_soon_for(grant, store, load_vertical(), today=TODAY)
    acronyms = [p["acronym"] for org in body["items"] for p in org["projects"]]
    assert acronyms == ["WIND"]
    assert store.pending_track_records() == []


def test_an_older_saved_ending_goes_back_to_the_live_calculation(tmp_path):
    from app.partners.precompute import compute_and_save

    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    grant = _grant(id="old-call", deadline_at=datetime(2027, 1, 31, tzinfo=UTC))
    store.upsert_opportunities([grant])
    _load(store, [_project("h2020:1", "2027-05-01")])
    compute_and_save(grant, store, load_vertical())
    saved = store.saved_track_record("old-call")
    saved["computed_at"] = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    store.save_track_record("old-call", saved)
    clear_track_record_cache()
    body = ending_soon_for(grant, store, load_vertical(), today=TODAY)
    assert body["status"] == "ok"
    assert "old-call" in store.pending_track_records()


def test_a_tender_record_is_saved_without_ending(tmp_path):
    from app.partners.precompute import compute_and_save

    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    tender = Opportunity(
        id="tender-call",
        source_id="ted",
        external_id="1",
        url="https://ted.europa.eu/1",
        title="Cable",
        type=OpportunityType.tender,
        kind=OpportunityKind.tender,
        subsectors=["offshore-wind"],
    )
    store.upsert_opportunities([tender])
    compute_and_save(tender, store, load_vertical())
    assert "ending" not in (store.saved_track_record("tender-call") or {})
