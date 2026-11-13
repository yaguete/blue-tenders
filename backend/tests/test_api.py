from fastapi.testclient import TestClient

from app.main import app


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
