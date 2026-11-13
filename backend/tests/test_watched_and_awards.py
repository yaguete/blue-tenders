from app.models.opportunity import Fact, FactOrigin, NoticeKind, Opportunity, OpportunityType
from app.sources.boamp import BoampSource, boamp_decision
from app.sources.boe import BoeSource, items
from app.sources.contracts_finder import ContractsFinderSource
from app.sources.fts import FtsSource
from app.sources.ocds import keep_release, release_action
from app.sources.watched import visible_text
from app.store import FileStore


def test_the_same_text_with_different_bytes_does_not_look_like_a_change():
    first = "<html><script>nonce-1</script><main>Calls for tender</main></html>"
    second = "<html><script>nonce-2</script><main>Calls for tender</main></html>"
    assert visible_text(first, "main") == visible_text(second, "main")


def test_an_award_with_the_same_procedure_shows_the_winner(tmp_path):
    store = FileStore(tmp_path / "opportunities.json")
    call = Opportunity(
        id="call",
        source_id="ted",
        external_id="1",
        url="https://ted.europa.eu/1",
        title="Cable",
        call_id="proc-1",
        deadline_at=__import__("datetime").datetime(2026, 12, 1, tzinfo=__import__("datetime").UTC),
    )
    award = Opportunity(
        id="award",
        source_id="ted",
        external_id="2",
        url="https://ted.europa.eu/2",
        title="Cable award",
        type=OpportunityType.award,
        notice=NoticeKind.award_notice,
        call_id="proc-1",
        facts=[Fact(field="winner_name", value="Grid Co", origin=FactOrigin.source, confidence=0.9)],
    )
    store.upsert_opportunities([call, award])
    found = store.awards_for("proc-1")
    assert found[0]["winner"] == "Grid Co"


def test_new_sources_map_a_record_without_inventing_a_deadline():
    uk = FtsSource().to_tender(
        {"ocid": "ocds-1", "tender": {"title": "Offshore wind survey", "description": "Survey"}}
    )
    assert uk.country == "GB"
    assert uk.deadline_at is None
    boe = BoeSource().to_tender({"identificador": "BOE-A-2026-1", "titulo": "Bases de eólica marina"})
    assert boe.notice.value == "pin"
    assert boe.deadline_at is None
    fr = BoampSource().to_tender({"idweb": "26-1", "objet": "Éolien en mer"})
    assert fr.country == "FR"
    assert fr.deadline_at is None


def test_real_fixtures_keep_currency_deadline_and_skip_awards():
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures"
    release = json.loads((fixture / "fts" / "release.json").read_text())
    assert keep_release(release)
    assert not keep_release({"tag": ["award", "contract"], "ocid": "x"})
    assert release_action({"tag": ["tenderCancellation"], "ocid": "ocds-1"}) == "cancel"
    same = FtsSource().to_tender({"ocid": "ocds-1", "tag": ["tender"], "tender": {"title": "Cable"}})
    again = FtsSource().to_tender({"ocid": "ocds-1", "tag": ["tenderUpdate"], "tender": {"title": "Cable"}})
    assert same.id == again.id
    uk = FtsSource().to_tender(release)
    assert uk.budget is not None
    assert uk.budget.currency == "GBP"
    assert uk.budget.amount_eur is None
    assert uk.deadline_at is not None and uk.deadline_at.year == 2027
    assert uk.dedupe_key == release["ocid"]
    assert uk.published_at is not None
    cf = ContractsFinderSource().to_tender(
        json.loads((fixture / "contracts_finder" / "release.json").read_text())
    )
    assert cf.source_id == "contracts-finder"
    assert cf.country == "GB"

    record = json.loads((fixture / "boamp" / "record.json").read_text())
    assert boamp_decision(record) == "keep"
    assert boamp_decision({**record, "famille": "JOUE"}) == "eu"
    assert boamp_decision({**record, "nature": "ATTRIBUTION"}) == "skip"
    fr = BoampSource().to_tender(record)
    assert fr.deadline_at is not None and fr.deadline_at.day == 4
    assert fr.published_at is not None

    found = items(json.loads((fixture / "boe" / "summary.json").read_text()))
    assert [row["identificador"] for row in found] == ["BOE-B-2026-1"]
    notice = BoeSource().to_tender({**found[0], "published_at": "2026-11-13"})
    assert notice.published_at is not None
    assert notice.published_at.isoformat() == "2026-11-13"
    assert notice.deadline_at is None
