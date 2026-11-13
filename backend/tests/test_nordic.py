import json
from datetime import date
from pathlib import Path

import httpx

from app.pipeline.run import prefilter
from app.settings import settings
from app.sources.base import source_subsectors
from app.sources.doffin import DoffinSource, doffin_keep, public_params
from app.sources.tenderned import TendernedSource, tenderned_keep
from app.vertical import load_vertical

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


def test_tenderned_marks_only_hits_that_name_the_term(monkeypatch):
    """Aviso real: la búsqueda de "wind op zee" lo trajo y su texto no nombra el sector."""
    loose = json.loads((FIXTURES / "tenderned" / "loose_hit.json").read_text())
    vertical = load_vertical()
    wind = {
        **loose,
        "publicatieId": "449001",
        "aanbestedingNaam": "Onderzoek wind op zee",
        "opdrachtBeschrijving": "Effectonderzoek voor de locatie van wind op zee.",
    }

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            rows = [dict(loose)]
            if params["search"] == "wind op zee":
                rows.append(wind)
            return httpx.Response(
                200, json={"content": rows, "last": True}, request=httpx.Request("GET", url)
            )

    monkeypatch.setattr("app.sources.tenderned.httpx.Client", Client)
    raws = list(TendernedSource().fetch(date(2026, 10, 1), vertical))
    marks = {raw.get("publicatieId"): source_subsectors(raw) for raw in raws}
    assert marks["444232"] == []
    assert marks["449001"] == ["offshore-wind"]
    items = [TendernedSource().to_tender(raw) for raw in raws]
    assert [item.external_id for item in prefilter(items, vertical)] == ["449001"]


def test_doffin_marks_only_hits_that_name_the_term(monkeypatch):
    monkeypatch.setattr(settings, "doffin_api_key", "")
    vertical = load_vertical()
    real = json.loads((FIXTURES / "doffin" / "notice.json").read_text())
    havvind = {
        **real,
        "sentToTed": False,
        "publicationDate": "2026-11-05",
        "type": "COMPETITION",
        "allTypes": ["COMPETITION"],
    }
    software = {
        "id": "2026-1",
        "heading": "Leveranse av lisenser for programvare",
        "description": "Rammeavtale for lisenser.",
        "publicationDate": "2026-11-05",
        "sentToTed": False,
        "type": "COMPETITION",
        "allTypes": ["COMPETITION"],
    }

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            rows = [dict(software)]
            if json["searchString"] == "havvind":
                rows.append(havvind)
            return httpx.Response(
                200,
                json={"hits": rows, "numHitsTotal": len(rows)},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("app.sources.doffin.httpx.Client", Client)
    raws = list(DoffinSource().fetch(date(2026, 11, 1), vertical))
    marks = {raw.get("id"): source_subsectors(raw) for raw in raws}
    assert marks["2026-1"] == []
    assert marks["2022-621509"] == ["offshore-wind"]
    items = [DoffinSource().to_tender(raw) for raw in raws]
    assert [item.external_id for item in prefilter(items, vertical)] == ["2022-621509"]
