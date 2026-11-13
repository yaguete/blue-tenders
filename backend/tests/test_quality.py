from datetime import UTC

from app.models.opportunity import Fact, FactOrigin, Opportunity
from app.quality.text import is_meta, is_thin, plain_text
from app.quality.validate import extractions_agree, quote_in_text, validate_opportunity, verify_fact


def _opp(**kwargs) -> Opportunity:
    base = {"id": "1", "source_id": "t", "external_id": "1", "url": "https://example.test", "title": "Call"}
    base.update(kwargs)
    return Opportunity(**base)


def test_opening_after_deadline_is_rejected():
    from datetime import datetime

    item = _opp(
        opens_at=datetime(2026, 5, 2, tzinfo=UTC),
        deadline_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert any("opens_at" in error for error in validate_opportunity(item))


def test_quote_must_appear_in_the_document():
    text = "Pre-proposal submission deadline: 16 November 2026, 15:00 CET in Brussels."
    assert quote_in_text("Pre-proposal submission deadline: 16 November 2026, 15:00 CET", text)
    assert not quote_in_text("deadline is 1 January 1999", text)


def test_unverified_llm_quote_drops_confidence():
    fact = Fact(field="deadline_at", value="x", origin=FactOrigin.llm, confidence=0.9, quote="not in text")
    checked = verify_fact(fact, "the document says something else entirely")
    assert checked.confidence <= 0.3
    assert checked.quote is None


def test_two_extractions_flag_the_deadline():
    assert extractions_agree({"deadline_at": "a", "cofunding_min": 70}, {"deadline_at": "b", "cofunding_min": 70}) == [
        "deadline_at"
    ]


def test_plain_text_strips_heading_marks():
    assert plain_text("## Expected Outcome: World-class hubs across the Union.") == (
        "Expected Outcome: World-class hubs across the Union."
    )
    assert plain_text("### Idea central\nTexto") == "Idea central\nTexto"


def test_plain_text_unwraps_emphasis_links_and_bullets():
    assert plain_text("**TRL 8** and _no change_ here") == "TRL 8 and _no change_ here"
    assert plain_text("See [the portal](https://example.test) for details") == "See the portal for details"
    assert plain_text("- First bullet\n- Second bullet") == "First bullet\nSecond bullet"


def test_plain_text_decodes_html_entities():
    assert plain_text("L&#8217;affidamento &amp; &#8220;cold ironing&#8221;") == "L’affidamento & “cold ironing”"


def test_plain_text_keeps_content_and_plain_numbers():
    assert plain_text("2 * 3 = 6") == "2 * 3 = 6"
    assert plain_text("snake_case_field stays") == "snake_case_field stays"
    assert plain_text(None) == ""
    assert plain_text("  spaced   out  ") == "spaced out"


def test_meta_summaries_are_caught_and_a_real_topic_summary_is_not():
    assert is_meta("The provided text is only a title, so this summary cannot cover them")
    assert is_meta("The text is only a title for a call concerning cables")
    assert is_meta("The provided text is a single short fragment and no other details are given")
    assert is_meta("The notice does not specify the budget")
    assert is_meta("This summary cannot cover scope")
    assert not is_meta("Project results are expected to improve wave energy devices.")


def test_a_title_and_boilerplate_are_thin_sources():
    assert is_thin("Only a title", "Only a title")
    assert is_thin("Conforme especificaciones PCAP", "Supply of a lidar")
    assert not is_thin(
        "Project results are expected to improve the reliability, availability and survivability of wave energy devices operating at sea.",
        "Wave energy",
    )
