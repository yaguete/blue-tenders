from app.models.opportunity import NoticeKind, Opportunity, OpportunityType
from app.store import FileStore, SupabaseStore
from tests.fake_supabase import FakeSupabase


def _bundle(source: str, project_id: str, org_id: str = "999") -> tuple:
    org = {"id": org_id, "pic": org_id, "name": "Wave Lab", "country": "PT", "activity_type": "REC", "sme": False}
    project = {
        "id": project_id,
        "source": source,
        "cordis_id": project_id.split(":")[-1],
        "programme_id": "h2020",
        "acronym": "WET",
        "title": "Wave energy",
        "objective": "A tidal turbine at sea",
        "topics": ["LCE-03-2015"],
        "topic_title": "Ocean energy",
        "end_date": "2019-09-30",
        "end_year": 2019,
        "subsectors": ["ocean-energy"],
        "url": "https://cordis.europa.eu/project/id/1",
    }
    part = {"org_id": org_id, "project_id": project_id, "role": "coordinator"}
    return org, project, part


def test_file_store_keeps_both_dumps_and_drops_what_left_the_cut(tmp_path):
    store = FileStore(tmp_path / "opportunities.json")
    org, project, part = _bundle("cordis-h2020", "h2020:1")
    store.replace_cordis("cordis-h2020", [org], [project], [part], {"content_hash": "a", "projects": 1})
    other, other_project, other_part = _bundle("cordis-horizon-europe", "horizon-europe:2", org_id="888")
    store.replace_cordis(
        "cordis-horizon-europe", [other], [other_project], [other_part], {"content_hash": "b", "projects": 1}
    )
    # El mismo volcado, ahora sin el proyecto: la organización compartida no se borra por el otro.
    store.replace_cordis("cordis-h2020", [org], [], [], {"content_hash": "c", "projects": 0})
    rows = store.cordis_participations()
    assert [row["project_id"] for row in rows] == ["horizon-europe:2"]
    assert store.track_record_sources()["cordis-h2020"]["content_hash"] == "c"
    assert "participations" not in store.load()
    assert not (tmp_path / "opportunities.json").exists()


def test_supabase_store_reads_the_same_rows():
    store = SupabaseStore(client=FakeSupabase())
    org, project, part = _bundle("cordis-h2020", "h2020:1")
    store.replace_cordis("cordis-h2020", [org], [project], [part], {"content_hash": "a", "projects": 1})
    # Una participación que ya no está: se quita después de insertar, no antes.
    store.replace_cordis("cordis-h2020", [org], [project], [], {"content_hash": "b", "projects": 1})
    assert store.cordis_participations() == []
    store.replace_cordis("cordis-h2020", [org], [project], [part], {"content_hash": "c", "projects": 1})
    row = store.cordis_participations()[0]
    assert row["org_name"] == "Wave Lab"
    assert row["topics"] == ["LCE-03-2015"]
    assert row["end_year"] == 2019
    assert row["role"] == "coordinator"
    assert row["demo"] is False
    award = Opportunity(
        id="award-1",
        source_id="ted",
        external_id="1",
        url="https://ted.europa.eu/1",
        title="Cable award",
        type=OpportunityType.award,
        notice=NoticeKind.award_notice,
    )
    store.client.table("opportunities").insert([award.model_dump(mode="json")]).execute()
    assert store.award_notices()[0].id == "award-1"
    assert store.load().get("participations", []) == []
