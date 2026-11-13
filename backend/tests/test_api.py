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


def test_legacy_tenders_redirect():
    client = TestClient(app)
    response = client.get("/tenders", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"].endswith("/opportunities")
