import threading
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api import opportunities as api
from app.main import app
from app.models.opportunity import Opportunity, OpportunityKind, OpportunityType


def test_search_returns_the_seeded_call():
    # Con `with` arranca el lifespan, que siembra la demo cuando el almacén está vacío (CI).
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["ok"] is True
        assert "sources" in health
        body = client.get("/opportunities").json()
        assert body["total"] >= 1
        assert any(item["programme_id"] == "sbep" for item in body["items"])


def test_stats_is_not_captured_by_the_detail_route():
    with TestClient(app) as client:
        response = client.get("/opportunities/stats")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "open",
        "closing_soon",
        "upcoming",
        "closed",
        "sources",
        "checked_at",
        "open_budget_eur",
    }


def test_negative_offset_is_rejected():
    client = TestClient(app)
    assert client.get("/opportunities", params={"offset": -1}).status_code == 422


def test_legacy_tenders_redirect():
    client = TestClient(app)
    response = client.get("/tenders", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"].endswith("/opportunities")


class _SlowStore:
    def __init__(self, fail: bool = False):
        self.calls = 0
        self.fail = fail

    def opportunities(self):
        self.calls += 1
        time.sleep(0.2)
        if self.fail:
            raise TimeoutError("statement timeout")
        return ["fresh"]


@pytest.fixture
def empty_cache(monkeypatch):
    monkeypatch.setattr(api, "_CACHE", {"at": 0.0, "items": None})


def test_concurrent_requests_read_the_table_once(monkeypatch, empty_cache):
    store = _SlowStore()
    monkeypatch.setattr(api, "get_store", lambda: store)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(api.cached_opportunities())) for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert store.calls == 1
    assert results == [["fresh"]] * 8


def test_failed_reload_serves_the_previous_copy(monkeypatch, empty_cache):
    api._CACHE.update({"at": time.monotonic() - api._CACHE_TTL - 1, "items": ["old"]})
    store = _SlowStore(fail=True)
    monkeypatch.setattr(api, "get_store", lambda: store)
    assert api.cached_opportunities() == ["old"]
    assert api.cached_opportunities() == ["old"]
    assert store.calls == 1


def _call(call_id: str, kind: OpportunityKind) -> Opportunity:
    return Opportunity(
        id=call_id,
        source_id="eu-ft",
        external_id=call_id,
        url=f"https://example.com/{call_id}",
        title=call_id,
        type=OpportunityType.grant if kind == OpportunityKind.grant else OpportunityType.tender,
        kind=kind,
    )


def test_wrapping_up_keeps_grants_with_a_count_and_marks_the_card(monkeypatch):
    soon = (date.today() + timedelta(days=20)).isoformat()
    computed = date.today().isoformat()
    grant = _call("grant-yes", OpportunityKind.grant)
    other = _call("grant-no", OpportunityKind.grant)
    tender = _call("tender-yes", OpportunityKind.tender)
    monkeypatch.setattr(api, "cached_opportunities", lambda: [grant, other, tender])
    monkeypatch.setattr(
        api,
        "cached_endings",
        lambda: {
            "grant-yes": {"computed_at": computed, "relevant": [["111", soon], ["111", soon]]},
            "tender-yes": {"computed_at": computed, "relevant": [["999", soon]]},
        },
    )
    filtered = api.search(wrapping_up=True)
    assert [row["id"] for row in filtered["items"]] == ["grant-yes"]
    assert filtered["items"][0]["wrapping_up"] == 1
    plain = {row["id"]: row for row in api.search()["items"]}
    assert plain["grant-yes"]["wrapping_up"] == 1
    assert "wrapping_up" not in plain["grant-no"]
    assert "wrapping_up" not in plain["tender-yes"]
