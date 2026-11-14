"""El chat de una ficha sabe lo mismo que la ficha sobre organizaciones."""

from datetime import UTC, date, datetime, timedelta

from app.assistant.chat import _partners
from app.assistant.prompt import build_request, for_provider, partners_note
from app.models.opportunity import Opportunity, OpportunityKind, OpportunityType
from app.partners.track_record import clear_track_record_cache
from app.store import FileStore

TRACK = {
    "status": "ok",
    "source": "cordis",
    "total": 3,
    "projects_total": 2,
    "projects": [
        {
            "id": "he:1",
            "acronym": "AENEAS",
            "title": "innovAtive ENErgy storage systems onboArd vesselS",
            "programme_id": "horizon-europe",
            "end_year": 2026,
            "evidence": "similar_text",
            "partners": [
                {"org_name": "FLANDERS MAKE", "country": "BE", "role": "coordinator", "also": []},
                {"org_name": "CORVUS ENERGY AS", "country": "NO", "role": "participant", "also": ["NEMOSHIP"]},
            ],
        }
    ],
}
ENDING = {
    "status": "ok",
    "window_months": 9,
    "consortia": [
        {
            "id": "he:2",
            "acronym": "AUTOFLEX",
            "title": "AUTOnomous small and FLEXible vessels",
            "programme_id": "horizon-europe",
            "end_date": "2026-12-31",
            "partners": [
                {"org_name": "SINTEF OCEAN AS", "country": "NO", "role": "coordinator", "relevant": True},
                {"org_name": "DFDS AS", "country": "DK", "role": "participant", "relevant": False},
            ],
        }
    ],
}


def _opp(**kwargs) -> Opportunity:
    base = {
        "id": "call",
        "source_id": "eu-ft",
        "external_id": "HORIZON-CL5-2027-D2-01",
        "url": "https://ec.europa.eu/call",
        "title": "Enhanced electric operation and battery durability",
        "type": OpportunityType.grant,
        "kind": OpportunityKind.grant,
        "subsectors": ["fleet-decarbonisation"],
        "language": "en",
        "deadline_at": datetime.now(UTC) + timedelta(days=60),
    }
    base.update(kwargs)
    return Opportunity(**base)


def test_the_note_lists_projects_consortia_and_awards():
    awards = [{"title": "Lot 1 – shore power", "winner": "Port Power SL", "amount_eur": 1_200_000}]
    text = partners_note(TRACK, ENDING, awards)
    assert "AENEAS — innovAtive ENErgy storage systems onboArd vesselS" in text
    assert "FLANDERS MAKE (BE; coordinator)" in text
    assert "CORVUS ENERGY AS (NO; also in NEMOSHIP)" in text
    assert "These are the 1 most similar of 2." in text
    assert "AUTOFLEX" in text and "ends 2026-12-31" in text
    assert "SINTEF OCEAN AS (NO; coordinator; also among the similar projects)" in text
    assert "DFDS AS (DK)" in text
    assert "Lot 1 – shore power (Port Power SL, EUR 1,200,000)" in text


def test_nothing_known_sends_nothing_and_none_found_is_said():
    assert partners_note(None, None, []) == ""
    assert partners_note({"status": "not_loaded", "source": "cordis"}, None, []) == ""
    text = partners_note({"status": "no_match", "source": "cordis"}, {"status": "no_match", "window_months": 9}, [])
    assert "Similar past projects or awards: none found." in text
    assert "ending in the next 9 months: none found." in text


def test_the_note_goes_after_the_call_data_and_deepseek_gets_no_cache_mark():
    note = partners_note(TRACK, ENDING, [])
    request = build_request(_opp(), "Who is wrapping up?", [], [], [], "", note)
    texts = [block for block in request["messages"][0]["content"] if block["type"] == "text"]
    record = next(index for index, block in enumerate(texts) if block["text"].startswith("About this call"))
    assert texts[record + 1]["text"] == note
    assert texts[record + 1]["cache_control"]["type"] == "ephemeral"
    plain = for_provider(request, deepseek=True)
    assert all("cache_control" not in block for block in plain["messages"][0]["content"])
    general = build_request(None, "What closes soon?", [], [], [], "", note)
    assert note not in " ".join(block.get("text") or "" for block in general["messages"][0]["content"])


def test_the_chat_reads_what_the_call_page_shows(tmp_path):
    clear_track_record_cache()
    store = FileStore(tmp_path / "opportunities.json")
    end = (date.today() + timedelta(days=90)).isoformat()
    project = {
        "id": "h2020:1",
        "source": "cordis-h2020",
        "programme_id": "h2020",
        "acronym": "SHIPCHARGE",
        "title": "Charging for electric ferries",
        "subsectors": ["fleet-decarbonisation"],
        "url": "https://cordis.europa.eu/project/id/1",
        "end_date": end,
    }
    orgs = [{"id": "111", "pic": "111", "name": "Ferry Lab", "country": "ES", "activity_type": "REC", "sme": False}]
    parts = [{"org_id": "111", "project_id": "h2020:1", "role": "coordinator"}]
    store.replace_cordis("cordis-h2020", orgs, [project], parts, {"loaded_at": "2026-11-11T00:00:00+00:00", "projects": 1})
    item = _opp()
    store.upsert_opportunities([item])
    text = _partners(store, store.get(item.id))
    assert "SHIPCHARGE" in text
    assert f"ends {end}" in text
    assert "Ferry Lab (ES; coordinator)" in text
