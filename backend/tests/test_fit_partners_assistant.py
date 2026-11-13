from app.assistant.engine import answer_about_opportunity, refuses_eligibility_promise
from app.catalog import rule_for
from app.enrich.rules import apply_programme_rules
from app.matching.fit import explain_fit
from app.models.opportunity import Analysis, AnalysisBlock, Opportunity, OpportunityKind
from app.partners.score import rank_organisations, score_project


def _opp(**kwargs) -> Opportunity:
    base = {
        "id": "1",
        "source_id": "t",
        "external_id": "1",
        "url": "https://example.test/call",
        "title": "Offshore wind call",
    }
    base.update(kwargs)
    return Opportunity(**base)


def test_fit_marks_a_country_mismatch_ineligible():
    item = _opp(eligible_countries=["ES"], country="ES", subsectors=["offshore-wind"])
    fit = explain_fit(item, {"country": "US", "entity_type": "sme", "subsectors": ["offshore-wind"]})
    assert fit["level"] == "likely_ineligible"
    assert "US" in fit["line"]


def test_fit_accepts_eu27_group_for_portugal():
    item = _opp(eligible_countries=["EU27"], subsectors=["offshore-wind"], eligible_entity_types=["ngo"])
    fit = explain_fit(
        item,
        {"country": "PT", "entity_type": "foundation", "subsectors": ["offshore-wind"]},
    )
    assert fit["level"] == "strong"
    assert "Portugal" not in fit["line"]
    assert "PT" in fit["line"]


def test_ria_rule_fills_consortium_but_not_a_deadline():
    item = _opp(programme_id="horizon-europe", type_of_action="RIA")
    apply_programme_rules(item)
    assert item.consortium_required is True
    assert item.consortium_min_countries == 3
    assert item.deadline_at is None
    assert rule_for("horizon-europe", "RIA").id == "horizon-europe-ria"


def test_partner_rank_prefers_the_closer_project():
    item = _opp(summary_en="floating offshore wind farm export cable", subsectors=["offshore-wind"], programme_id="horizon-europe")
    rows = [
        {
            "org_name": "Far Lab",
            "country": "NO",
            "activity_type": "REC",
            "role": "participant",
            "acronym": "OTHER",
            "title": "Urban cycling survey",
            "objective": "bicycles in cities",
            "end_year": 2024,
            "programme_id": "horizon-europe",
            "subsectors": [],
            "url": "https://cordis.europa.eu/project/id/1",
        },
        {
            "org_name": "Near Lab",
            "country": "DK",
            "activity_type": "REC",
            "role": "coordinator",
            "acronym": "FLOAT",
            "title": "Floating offshore wind",
            "objective": "export cable and floating offshore wind farm",
            "end_year": 2025,
            "programme_id": "horizon-europe",
            "subsectors": ["offshore-wind"],
            "url": "https://cordis.europa.eu/project/id/2",
        },
    ]
    ranked = rank_organisations(item, rows)
    assert ranked[0]["org_name"] == "Near Lab"
    assert score_project(item, rows[1])["score"] > score_project(item, rows[0])["score"]


def test_assistant_does_not_promise_eligibility():
    item = _opp(
        kind=OpportunityKind.grant,
        summary_en="Open to research organisations.",
        analysis=Analysis(
            summary="Open to research organisations.",
            blocks=[AnalysisBlock(heading="Eligibility", text="Research organisations may apply.", origin="extracted")],
        ),
    )
    answer = answer_about_opportunity(item, "Are we eligible as a Portuguese foundation?")
    assert refuses_eligibility_promise(answer.text)
    assert "eligible" not in answer.text.lower() or "not a determination" in answer.text.lower()
    assert answer.citations
