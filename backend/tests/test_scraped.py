from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.models.opportunity import Opportunity
from app.sources.dates import parse_when
from app.sources.scraped import (
    ScrapedSource,
    _detail_fields,
    drop_message,
    parse_amount,
    rows_from_html,
    rows_from_rss,
)

FIXTURES = Path(__file__).parent / "fixtures" / "scraped"
CONFIG = Path(__file__).resolve().parents[2] / "config" / "scraped"


def test_french_and_danish_months_are_read_without_the_container_locale():
    french = parse_when("15 décembre 2026", "fr", ["%d %B %Y"], "Europe/Paris")
    assert french is not None
    assert french.day == 15 and french.month == 12 and french.tzinfo is not None
    danish = parse_when("15. januar 2027", "da", ["%d. %B %Y"], "Europe/Copenhagen")
    assert danish is not None
    assert danish.day == 15 and danish.month == 1 and danish.year == 2027
    assert parse_when("un mes desde la publicación", "es", ["%d de %B de %Y"], "Europe/Madrid") is None


def test_cinea_listing_reads_the_deadline_from_the_real_page():
    spec = yaml.safe_load((CONFIG / "cinea.yaml").read_text())
    rows = rows_from_html((FIXTURES / "cinea.html").read_text(), spec, spec["url"])
    assert len(rows) == 1
    assert "Maritime Spatial Planning" in rows[0]["title"]
    assert rows[0]["link"].startswith("https://cinea.ec.europa.eu/")
    item = ScrapedSource(CONFIG / "cinea.yaml").to_tender(rows[0])
    assert item.deadline_at is not None
    assert item.deadline_at.year == 2027
    assert item.deadline_at.tzinfo == UTC or item.deadline_at.utcoffset() is not None
    fact = next(fact for fact in item.facts if fact.field == "deadline_at")
    assert fact.origin.value == "scraped"
    assert fact.quote
    assert fact.confidence == 0.85


def test_mercator_rss_and_detail_keep_the_closing_time():
    spec = yaml.safe_load((CONFIG / "mercator.yaml").read_text())
    rows = rows_from_rss((FIXTURES / "mercator.xml").read_bytes(), spec)
    assert rows and rows[0]["link"].startswith("https://www.mercator-ocean.eu/tender/")
    extra = _detail_fields((FIXTURES / "mercator_detail.html").read_text(), spec["detail"]["fields"])
    assert extra["deadline_text"] == "30 Sep 2026 12:00 pm"
    rows[0]["deadline_text"] = extra["deadline_text"]
    item = ScrapedSource(CONFIG / "mercator.yaml").to_tender(rows[0])
    assert item.deadline_at is not None
    assert item.deadline_at.day == 30 and item.deadline_at.month == 9
    assert item.deadline_at.hour == 12
    assert item.country == "FR"


def test_an_amount_without_a_clear_currency_stays_unqualified():
    amount, currency = parse_amount("12 000 000 kr")
    assert amount == 12000000
    assert currency is None
    amount, currency = parse_amount("EUR 1.200.000")
    assert amount == 1200000 and currency == "EUR"


def test_a_listing_that_drops_to_zero_is_a_page_change():
    assert drop_message(3, 0)
    assert drop_message(None, 0) is None
    assert drop_message(3, 1) is None


def _spec(name: str) -> dict:
    return yaml.safe_load((CONFIG / name).read_text())


def test_the_other_listings_read_the_saved_pages():
    eudp = _spec("eudp.yaml")
    rows = rows_from_html((FIXTURES / "eudp.html").read_text(), eudp, eudp["url"])
    assert rows[0]["title"] == "Indkaldelse til EUDP 2026-II"
    item = ScrapedSource(CONFIG / "eudp.yaml").to_tender(rows[0])
    assert item.deadline_at is not None
    assert item.deadline_at.day == 2 and item.deadline_at.month == 9 and item.deadline_at.hour == 12
    assert item.country == "DK"

    cet = _spec("cetpartnership.yaml")
    calls = rows_from_html((FIXTURES / "cet.html").read_text(), cet, cet["url"])
    assert [row["title"] for row in calls] == ["Joint Call 2026"]

    euro = _spec("interreg-euromed.yaml")
    assert rows_from_html((FIXTURES / "euromed.html").read_text(), euro, euro["url"]) == []
    euro_open = {**euro, "skip_if": {}}
    kept = rows_from_html((FIXTURES / "euromed.html").read_text(), euro_open, euro["url"])
    assert kept[0]["deadline_text"] == "01/06/2022"

    nwe = _spec("interreg-nwe.yaml")
    assert rows_from_html((FIXTURES / "nwe.html").read_text(), nwe, nwe["url"]) == []

    ukri = _spec("ukri.yaml")
    feed = rows_from_rss((FIXTURES / "ukri.xml").read_bytes(), ukri)
    extra = _detail_fields((FIXTURES / "ukri_detail.html").read_text(), ukri["detail"]["fields"])
    feed[0]["deadline_text"] = extra["deadline_text"]
    item = ScrapedSource(CONFIG / "ukri.yaml").to_tender(feed[0])
    assert item.deadline_at is not None
    assert item.deadline_at.year == 2027 and item.deadline_at.month == 3 and item.deadline_at.day == 23
    assert item.country == "GB"


def test_a_programme_page_bypasses_keywords_and_a_past_deadline_does_not_create_a_card(tmp_path, monkeypatch):
    from app.pipeline.run import prefilter, split_eu
    from app.sources.base import source_subsectors
    from app.store import FileStore
    from app.vertical import load_vertical

    store = FileStore(tmp_path / "opportunities.json")
    monkeypatch.setattr("app.store.get_store", lambda: store)
    source = ScrapedSource(CONFIG / "eudp.yaml")
    item = source.to_tender(
        {"title": "Indkaldelse til EUDP 2026-II", "link": "https://www.eudp.dk/soeg-tilskud/indkaldelse-til-eudp"}
    )
    assert "offshore-wind" in source_subsectors(item.raw)
    assert prefilter([item], load_vertical()) == [item]

    past = {"link": "https://www.eudp.dk/old", "deadline_text": "2. januar 2020"}
    assert source._past_and_new(past) is True
    kept = Opportunity(
        id=Opportunity.make_id("eudp", past["link"]),
        source_id="eudp",
        external_id=past["link"],
        url=past["link"],
        title="Old call",
        deadline_at=datetime(2020, 1, 2, tzinfo=UTC),
    )
    store.upsert_opportunities([kept])
    assert source._past_and_new(past) is False

    marked = item.model_copy(update={"raw": {**item.raw, "_skip_eu": True}})
    stay, gone = split_eu([item, marked])
    assert stay == [item]
    assert gone == [marked]
