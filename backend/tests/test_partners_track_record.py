from datetime import date

from app.api.opportunities import detail
from app.jobs import ted_awards
from app.models.opportunity import (
    Budget,
    Fact,
    FactOrigin,
    Opportunity,
    OpportunityKind,
    OpportunityType,
)
from app.partners.score import rank_track_record, specific_cpv
from app.partners.track_record import track_record_for
from app.sources.ted import TedSource
from app.store import FileStore, SupabaseStore
from app.vertical import load_vertical
from tests.fake_supabase import FakeSupabase

TOPIC = "HORIZON-CL5-2023-D3-02-15"


def _grant(**kwargs) -> Opportunity:
    base = {
        "id": "call",
        "source_id": "eu-ft",
        "external_id": TOPIC,
        "url": "https://ec.europa.eu/call",
        "title": "Critical technologies for offshore wind decommissioning",
        "title_en": "Critical technologies for offshore wind decommissioning",
        "summary_en": "Lifetime and circularity of offshore wind",
        "type": OpportunityType.grant,
        "kind": OpportunityKind.grant,
        "programme_id": "horizon-europe",
        "topic_id": TOPIC,
        "subsectors": ["offshore-wind"],
        "language": "en",
    }
    base.update(kwargs)
    return Opportunity(**base)


def _row(**kwargs) -> dict:
    base = {
        "org_name": "Wind Lab",
        "country": "ES",
        "activity_type": "REC",
        "pic": "111",
        "role": "coordinator",
        "acronym": "BLADE",
        "title": "Circular wind turbine blades",
        "objective": "offshore wind decommissioning",
        "topics": [TOPIC],
        "topic_title": "Critical technologies for offshore wind",
        "programme_id": "horizon-europe",
        "end_year": 2027,
        "subsectors": ["offshore-wind"],
        "url": "https://cordis.europa.eu/project/id/1",
        "project_id": "horizon-europe:1",
    }
    base.update(kwargs)
    return base


def test_same_topic_is_kept_and_another_call_does_not_inherit_it():
    cfg = load_vertical().track_record
    wind = _grant()
    other = _row(org_name="City Bikes", pic="222", acronym="BIKE", title="Urban cycling survey",
                 objective="bicycles in cities", topics=["OTHER"], topic_title="", subsectors=["ocean-energy"],
                 project_id="horizon-europe:2", programme_id="h2020")
    same = _row()
    ranked, total = rank_track_record(wind, [same, other], cfg=cfg, kind="cordis")
    assert total == 1
    assert ranked[0]["org_name"] == "Wind Lab"
    assert ranked[0]["projects"][0]["evidence"] == "same_topic"
    wave = _grant(
        id="wave",
        external_id="HORIZON-CL5-2023-D3-02-10",
        topic_id="HORIZON-CL5-2023-D3-02-10",
        title="Power take-off for wave energy devices",
        title_en="Power take-off for wave energy devices",
        summary_en="Control systems for wave energy",
        subsectors=["ocean-energy"],
    )
    ranked, _total = rank_track_record(wave, [same, other], cfg=cfg, kind="cordis")
    assert "Wind Lab" not in {row["org_name"] for row in ranked}


def test_a_cascade_does_not_inherit_the_parent_topic():
    cfg = load_vertical().track_record
    cascade = _grant(
        external_id="cascade-15802",
        topic_id=TOPIC,
        title="Open call for a regional hub",
        title_en="Open call for a regional hub",
        summary_en="A short note",
    )
    ranked, total = rank_track_record(
        cascade,
        [_row(title="QQQQ", objective="RRRR", topic_title="", topics=[TOPIC])],
        cfg=cfg,
    )
    assert total == 0
    assert ranked == []


def test_specific_cpv_matches_and_a_generic_division_does_not():
    assert "31321" in specific_cpv(["31321500"], 5)
    assert specific_cpv(["73000000"], 5) == set()
    cfg = load_vertical().track_record
    tender = Opportunity(
        id="tender",
        source_id="ted",
        external_id="1",
        url="https://ted.europa.eu/1",
        title="Curative maintenance of submarine cable links",
        title_en="France – Repair and maintenance services – Curative maintenance of submarine cable links",
        summary_en="Marine operations on submarine high voltage cables",
        kind=OpportunityKind.tender,
        subsectors=["subsea-cables"],
        cpv=["31321500"],
        call_id="this-procedure",
        language="en",
    )
    close = _row(
        org_name="DeepOcean AS",
        pic="aaa",
        title="Repair and maintenance services – Framework agreement for subsea cables",
        objective="Repair and jointing of submarine cable",
        subsectors=["subsea-cables"],
        topics=[],
        topic_title="",
        cpv=["31321500"],
        project_id="ted-1",
        role="winner",
        call_id="other-procedure",
    )
    generic = _row(
        org_name="Office Depot",
        pic="bbb",
        title="Office supplies",
        objective="Paper and toner",
        subsectors=["subsea-cables"],
        topics=[],
        cpv=["73000000"],
        project_id="ted-2",
        role="winner",
        call_id="another",
    )
    same_procedure = _row(**{**close, "org_name": "Same Procedure", "pic": "ccc", "project_id": "ted-3", "call_id": "this-procedure"})
    ranked, _total = rank_track_record(tender, [close, generic, same_procedure], cfg=cfg, kind="awards")
    names = {row["org_name"] for row in ranked}
    assert "DeepOcean AS" in names
    assert "Office Depot" not in names
    assert "Same Procedure" not in names


def test_empty_states_stay_distinct(tmp_path):
    vertical = load_vertical()
    store = FileStore(tmp_path / "opportunities.json")
    grant = _grant()
    assert track_record_for(grant, store, vertical)["status"] == "not_loaded"
    store.save_track_record_source("cordis-h2020", loaded_at="2026-11-11T00:00:00+00:00", projects=1)
    spanish = _grant(language="es", title="Eólica marina", title_en=None, summary_en=None)
    assert track_record_for(spanish, store, vertical)["status"] == "not_comparable"
    assert track_record_for(grant, store, vertical)["status"] == "no_match"
    tender = Opportunity(
        id="t",
        source_id="ted",
        external_id="1",
        url="https://ted.europa.eu/1",
        title="Lidar",
        kind=OpportunityKind.tender,
        subsectors=["offshore-wind"],
        language="fr",
    )
    assert track_record_for(tender, store, vertical)["status"] == "not_loaded"


def test_detail_reads_supabase_participations(monkeypatch):
    store = SupabaseStore(client=FakeSupabase())
    grant = _grant(id="live-call")
    store.client.table("opportunities").insert([grant.model_dump(mode="json")]).execute()
    store.replace_cordis(
        "cordis-horizon-europe",
        [{"id": "111", "pic": "111", "name": "Wind Lab", "country": "ES", "activity_type": "REC", "sme": False}],
        [{
            "id": "horizon-europe:1",
            "source": "cordis-horizon-europe",
            "programme_id": "horizon-europe",
            "acronym": "BLADE",
            "title": "Circular wind turbine blades",
            "objective": "offshore wind",
            "topics": [TOPIC],
            "topic_title": "Critical technologies",
            "end_date": "2027-11-30",
            "subsectors": ["offshore-wind"],
            "url": "https://cordis.europa.eu/project/id/1",
        }],
        [{"org_id": "111", "project_id": "horizon-europe:1", "role": "coordinator"}],
        {"loaded_at": "2026-11-11T00:00:00+00:00", "projects": 1},
    )
    monkeypatch.setattr("app.api.opportunities.get_store", lambda: store)
    body = detail("live-call")
    assert body["track_record"]["source"] == "cordis"
    assert body["track_record"]["status"] == "ok"
    assert body["partners"][0]["org_name"] == "Wind Lab"
    assert body["partners"][0]["demo"] is False
    assert body["partners"][0]["projects"][0]["url"].startswith("https://cordis.europa.eu/project/id/")


def test_ted_awards_job_does_not_touch_ingest_runs(tmp_path, monkeypatch):
    store = FileStore(tmp_path / "opportunities.json")

    class Silent(TedSource):
        def fetch(self, since, vertical):
            assert self.include_cpv is False
            assert "can-standard" in self.notice_types
            return []

    monkeypatch.setattr(ted_awards, "TedSource", lambda **kwargs: Silent(**kwargs))
    monkeypatch.setattr(ted_awards.pipeline, "index", lambda items: 0)
    ted_awards.run(days=365, today=date(2026, 11, 11), store=store)
    assert store.load()["ingest_runs"] == []
    assert store.track_record_sources()["ted-awards"]["since"] == "2025-11-11"


def test_the_normalized_mirror_only_keeps_cordis_orgs(tmp_path):
    from app.partners.precompute import compute_and_save
    from app.partners.track_record import clear_track_record_cache

    clear_track_record_cache()
    store = SupabaseStore(client=FakeSupabase())
    store.client.table("partner_orgs").insert(
        [{"id": "hash-1", "pic": "hash-1", "name": "Grid Co", "country": "NO", "activity_type": "PRC", "sme": True}]
    ).execute()
    award = Opportunity(
        id="award-1",
        source_id="ted",
        external_id="9-2026",
        url="https://ted.europa.eu/9",
        title="Cable repair",
        type=OpportunityType.award,
        call_id="PROC-9",
        cpv=["45315400"],
        subsectors=["subsea-cables"],
        language="en",
        facts=[
            Fact(
                field="winners",
                value=[
                    {"name": "Grid Co", "country": "NO", "size": "medium", "id_hash": "hash-1"},
                    {"name": "Unknown AS", "country": "NO", "size": "medium", "id_hash": None},
                ],
                origin=FactOrigin.source,
                confidence=0.9,
            )
        ],
    )
    viewed = Opportunity(
        id="tender-1",
        source_id="ted",
        external_id="8-2026",
        url="https://ted.europa.eu/8",
        title="Cable works",
        type=OpportunityType.tender,
        call_id="PROC-8",
        cpv=["45315400"],
        subsectors=["subsea-cables"],
        language="en",
    )
    store.upsert_opportunities([award, viewed])
    store.save_track_record_source("ted-awards", loaded_at="2026-11-11T00:00:00+00:00", projects=1)
    compute_and_save(viewed, store, load_vertical())
    rows = store.client.table("opportunity_partner_matches").select("*").execute().data or []
    # El espejo referencia partner_orgs: un ganador que no es organización CORDIS solo viaja en el registro.
    assert [row["org_id"] for row in rows] == ["hash-1"]


def test_an_award_notice_is_not_sent_to_the_model(monkeypatch):
    from app.pipeline.run import enrich

    called = []
    monkeypatch.setattr("app.enrich.analyse.analyse", lambda item: called.append("analyse") or item)
    monkeypatch.setattr("app.enrich.translate.translate", lambda item: called.append("translate") or item)
    award = Opportunity(
        id="a",
        source_id="ted",
        external_id="1",
        url="https://ted.europa.eu/1",
        title="Submarine cable repair",
        type=OpportunityType.award,
        subsectors=[],
        facts=[Fact(field="winner_name", value="DeepOcean AS", origin=FactOrigin.source, confidence=0.9)],
    )
    enrich([award], load_vertical())
    assert called == []


def test_a_placsp_award_shows_its_winner_against_the_call_budget(tmp_path):
    from pathlib import Path

    from app.partners.track_record import clear_track_record_cache
    from app.sources.placsp import PlacspSource

    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    xml = (Path(__file__).parent / "fixtures" / "placsp" / "award_entry.xml").read_text()
    award = PlacspSource().to_tender({"xml": xml, "status": "ADJ"})
    award.subsectors = ["green-ports"]
    call = Opportunity(
        id="the-call",
        source_id="placsp",
        external_id=award.call_id,
        url="https://contrataciondelestado.es/call",
        title="Shore power call",
        type=OpportunityType.tender,
        call_id=award.call_id,
        budget=Budget(amount=700_000, currency="EUR", amount_eur=700_000),
        subsectors=["green-ports"],
    )
    viewed = Opportunity(
        id="other-call",
        source_id="ted",
        external_id="2",
        url="https://ted.europa.eu/2",
        title="Shore power for another port",
        type=OpportunityType.tender,
        call_id="OTHER",
        cpv=["45315300"],
        subsectors=["green-ports"],
        language="en",
    )
    store.upsert_opportunities([call, award, viewed])
    body = track_record_for(viewed, store, load_vertical())
    project = body["items"][0]["projects"][0]
    assert body["items"][0]["org_name"] == "BONSAILAB SLU"
    assert project["amount_eur"] == 499_000
    assert project["base_amount_eur"] == 700_000
    assert project["contract_end"] == "2027-01-07"

    # La licitación no está guardada: el presupuesto del propio aviso no hace de base.
    alone = FileStore(tmp_path / "alone.json")
    alone.upsert_opportunities([award, viewed])
    missing = track_record_for(viewed, alone, load_vertical())
    assert missing["items"][0]["projects"][0]["base_amount_eur"] is None
    assert missing["items"][0]["projects"][0]["amount_eur"] == 499_000
