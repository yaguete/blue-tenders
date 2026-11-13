import json
from datetime import date
from pathlib import Path

from app.sources.doffin import DoffinSource, doffin_keep, public_params
from app.sources.tenderned import TendernedSource, tenderned_keep

FIXTURES = Path(__file__).parent / "fixtures"


def test_tenderned_reads_the_deadline_and_skips_european_notices():
    raw = json.loads((FIXTURES / "tenderned" / "notice.json").read_text())
    assert tenderned_keep(raw) == "eu"
    assert tenderned_keep({**raw, "europees": False}) == "keep"
    item = TendernedSource().to_tender(raw)
    assert item.country == "NL"
    assert item.deadline_at is not None
    assert item.deadline_at.day == 5 and item.deadline_at.hour == 9
    assert item.deadline_at.tzinfo is not None
    assert item.published_at is not None
    assert "windparken" in item.title
    assert item.buyer is not None


def test_the_public_search_is_a_get_with_notice_types():
    params = public_params(date(2026, 8, 15), "havvind", 1)
    assert ("searchString", "havvind") in params
    assert ("issueDateFrom", "2026-08-15") in params
    assert ("sortBy", "PUBLICATION_DATE_DESC") in params
    kinds = [value for key, value in params if key == "type"]
    assert kinds == ["COMPETITION", "ANNOUNCEMENT_OF_COMPETITION", "PRE_ANNOUNCEMENT"]
    assert "RESULT" not in kinds


def test_doffin_keeps_the_currency_and_skips_ted_and_awards():
    raw = json.loads((FIXTURES / "doffin" / "notice.json").read_text())
    assert doffin_keep(raw) == "eu"
    competition = {
        "id": "2024-105741",
        "heading": "Rammeavtale levering av HV sjøkabel med tilhørende materiell",
        "description": "Rammeavtale for levering av 172 kV sjøkabel.",
        "buyer": [{"name": "REN Sjøkabelberedskap AS"}],
        "estimatedValue": {"currencyCode": "NOK", "amount": 3600000000},
        "deadline": "2024-05-16T07:00:00Z",
        "publicationDate": "2024-04-22",
        "sentToTed": False,
        "type": "ANNOUNCEMENT_OF_COMPETITION",
        "allTypes": ["COMPETITION", "ANNOUNCEMENT_OF_COMPETITION"],
    }
    assert doffin_keep(competition) == "keep"
    item = DoffinSource().to_tender(competition)
    assert item.country == "NO"
    assert item.budget is not None
    assert item.budget.currency == "NOK"
    assert item.budget.amount_eur is None
    assert item.deadline_at is not None
    assert item.deadline_at.day == 16
    assert item.published_at is not None
