from datetime import date

from app.enrich.watched_draft import change_quote
from app.models.opportunity import FactOrigin, NoticeKind, OpportunityKind
from app.pipeline.run import prefilter
from app.settings import settings
from app.sources.base import SOURCE_SUBSECTORS
from app.sources.watched import WatchedSource, visible_text
from app.store import FileStore
from app.vertical import load_vertical


def test_every_matching_node_is_part_of_the_watched_text():
    html = "<article>one</article><nav>skip</nav><article>two</article>"
    assert visible_text(html, "article") == "one two"


def test_a_change_carries_the_day_and_the_page_subsectors(tmp_path, monkeypatch):
    folder = tmp_path / "config"
    folder.mkdir()
    (folder / "watched.yaml").write_text(
        """
- id: sbep
  url: https://example.test/sbep
  selector: main
  title: SBEP
  language: en
  kind: grant
  subsectors: [offshore-wind]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "config_dir", folder)
    store = FileStore(tmp_path / "opportunities.json")
    monkeypatch.setattr("app.store.get_store", lambda: store)
    html = {"body": "<main>Calls for tender</main>"}

    class Response:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class Client:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str):
            del url
            return Response(html["body"])

    monkeypatch.setattr("app.sources.watched.httpx.Client", Client)
    source = WatchedSource()
    vertical = load_vertical()
    assert list(source.fetch(date.min, vertical)) == []
    html["body"] = "<main>Offshore wind draft work programme</main>"
    found = list(source.fetch(date.min, vertical))
    assert len(found) == 1
    assert found[0]["detected_at"]
    assert found[0]["kind"] == "grant"
    assert found[0][SOURCE_SUBSECTORS] == ["offshore-wind"]
    assert list(source.fetch(date.min, vertical)) == []

    item = source.to_tender(found[0])
    assert item.notice == NoticeKind.pin
    assert item.deadline_at is None
    assert item.published_at is not None
    assert item.published_at.isoformat() == found[0]["detected_at"][:10]
    assert item.url == "https://example.test/sbep"
    fact = item.facts[0]
    assert fact.origin == FactOrigin.scraped
    assert fact.field == "seen_at"
    assert fact.document_url == item.url
    assert fact.quote and "wind" in fact.quote
    assert prefilter([item], vertical)


def test_without_subsectors_only_a_diff_that_names_the_sector_is_kept():
    source = WatchedSource()
    vertical = load_vertical()
    base = {
        "id": "horizon",
        "url": "https://example.test/wp",
        "title": "Horizon Europe work programmes",
        "detected_at": "2026-11-13T08:00:00+00:00",
        "language": "en",
        "previous": "Health cluster draft",
    }
    noise = source.to_tender({**base, "text": "Health cluster draft updated"})
    signal = source.to_tender({**base, "text": "Draft offshore wind work programme"})
    assert noise.deadline_at is None
    assert noise.published_at == date(2026, 11, 13)
    assert prefilter([noise], vertical) == []
    assert prefilter([signal], vertical)


def test_a_grant_page_stays_a_pin_and_a_page_without_kind_stays_a_tender():
    source = WatchedSource()
    base = {
        "id": "sbep",
        "url": "https://example.test/sbep",
        "title": "SBEP",
        "detected_at": "2026-11-13T08:00:00+00:00",
        "text": "Draft offshore wind work programme",
        "previous": "News",
    }
    grant = source.to_tender({**base, "kind": "grant"})
    assert grant.kind == OpportunityKind.grant
    assert grant.notice == NoticeKind.pin
    tender = source.to_tender(base)
    assert tender.kind == OpportunityKind.tender
    assert tender.notice == NoticeKind.pin


def test_a_page_without_a_seen_date_is_not_a_card():
    try:
        WatchedSource().to_tender({"id": "sbep", "url": "https://example.test", "title": "SBEP"})
    except ValueError as exc:
        assert "fecha" in str(exc)
    else:
        raise AssertionError("tenía que faltar la fecha")


def test_the_watch_job_publishes_a_pin(tmp_path, monkeypatch):
    from app.jobs.watch import run

    store = FileStore(tmp_path / "opportunities.json")
    monkeypatch.setattr("app.store.get_store", lambda: store)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "enrich_documents", False)
    raw = {
        "id": "sbep",
        "url": "https://bluepartnership.eu/",
        "title": "Sustainable Blue Economy Partnership",
        "text": "A draft offshore wind work programme is out for consultation",
        "previous": "News",
        "detected_at": "2026-11-13T08:00:00+00:00",
        "language": "en",
        SOURCE_SUBSECTORS: ["offshore-wind"],
    }
    monkeypatch.setattr(WatchedSource, "fetch", lambda self, since, vertical: [raw])
    assert run() == 1
    saved = store.opportunities()
    assert len(saved) == 1
    assert saved[0].notice == NoticeKind.pin
    assert saved[0].deadline_at is None
    assert saved[0].published_at == date(2026, 11, 13)
    assert saved[0].url == "https://bluepartnership.eu/"
    assert saved[0].subsectors == ["offshore-wind"]
    assert any(fact.origin == FactOrigin.scraped and fact.quote for fact in saved[0].facts)


def test_the_quote_is_only_the_new_words():
    assert "wind" in change_quote("Draft offshore wind call", "Draft call")
    assert "Draft" not in change_quote("Draft offshore wind call", "Draft call").split()
