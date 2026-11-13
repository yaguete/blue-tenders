import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.models.opportunity import DeadlineModel, OpportunityKind, OpportunityStatus
from app.settings import settings
from app.sources import REGISTRY
from app.sources.aides_territoires import (
    AidesTerritoiresSource,
    aid_kind,
    filters_bite,
    list_params,
)
from app.sources.terms import search_pairs
from app.vertical import load_vertical

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "aides_territoires" / "aid.json").read_text()
)


def _aid() -> dict:
    return json.loads(json.dumps(FIXTURE))


def test_the_source_is_registered_and_searches_the_configured_terms():
    assert "aides-territoires" in REGISTRY
    pairs = search_pairs(load_vertical(), "aides-territoires")
    assert ("offshore-wind", "éolien en mer") in pairs
    assert ("subsea-cables", "câble sous-marin") in pairs
    assert all(term != "port" for _, term in pairs)


def test_a_real_aid_keeps_the_deadline_and_drops_the_html():
    item = AidesTerritoiresSource().to_tender(_aid())
    assert item.external_id == "165655"
    assert item.country == "FR"
    assert item.kind == OpportunityKind.grant
    assert item.buyer is not None and item.buyer.name == "ADEME"
    assert item.published_at == date(2026, 1, 4)
    assert item.opens_at is not None and item.opens_at.day == 1 and item.opens_at.tzinfo is not None
    assert item.deadline_at is not None
    assert item.deadline_at.day == 31 and item.deadline_at.hour == 0
    assert item.deadline_at.tzinfo is not None
    assert item.url.startswith("https://agirpourlatransition.ademe.fr/")
    assert "<p>" not in (item.description or "")
    assert "l'ADEME" in (item.description or "")
    assert "hydrolien" in (item.description or "").casefold()
    assert any(doc.url.endswith(".pdf") for doc in item.documents)
    assert "Commune" in item.eligible_entity_types


def test_rates_are_percents_a_phrase_is_not_a_date_and_a_permanent_aid_stays_open():
    rated = _aid()
    rated["subvention_rate_lower_bound"] = 40
    rated["subvention_rate_upper_bound"] = 70
    item = AidesTerritoiresSource().to_tender(rated)
    assert item.cofunding_min == 40
    assert item.cofunding_max == 70

    prose = _aid()
    prose["submission_deadline"] = "fin 2026"
    assert AidesTerritoiresSource().to_tender(prose).deadline_at is None

    standing = _aid()
    standing["recurrence"] = "Ponctuelle"
    standing["submission_deadline"] = None
    standing["start_date"] = None
    standing["contact"] = "ada@example.com"
    kept = AidesTerritoiresSource().to_tender(standing)
    assert kept.deadline_model == DeadlineModel.continuous
    assert kept.deadline_at is None
    assert kept.status == OpportunityStatus.open
    assert "contact" not in kept.raw
    assert "ada@example.com" not in json.dumps(kept.raw)


def test_kind_follows_the_aid_type():
    assert aid_kind(["Subvention", "Ingénierie technique"]) == OpportunityKind.grant
    assert aid_kind(["Prêt"]) == OpportunityKind.loan
    assert aid_kind(["Subvention", "Prêt"]) == OpportunityKind.blended
    assert aid_kind(["Ingénierie technique"]) == OpportunityKind.technical_assistance


def test_the_text_filter_has_to_shrink_the_catalogue(monkeypatch):
    params = list_params("éolien en mer", 2)
    assert params["text"] == "éolien en mer"
    assert params["page"] == 2
    filters_bite(5, 3009)
    with pytest.raises(RuntimeError):
        filters_bite(3009, 3009)

    monkeypatch.setattr(settings, "aides_territoires_api_key", "")
    with pytest.raises(RuntimeError):
        list(AidesTerritoiresSource().fetch(date(2026, 11, 1), load_vertical()))

    monkeypatch.setattr(settings, "aides_territoires_api_key", "present")
    calls: list[dict] = []

    def _response(payload: dict) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=httpx.Request("GET", "https://aides-territoires.beta.gouv.fr/api/aids/"),
        )

    def post(url, headers=None, timeout=None):
        assert headers is not None
        assert headers["X-AUTH-TOKEN"] == "present"
        return _response({"token": "bearer"})

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            calls.append(dict(params or {}))
            if params and params.get("text"):
                return _response(
                    {
                        "count": 1,
                        "next": None,
                        "results": [
                            {"id": 165655, "name": "Éolien en mer", "is_live": True, "contact": "x"}
                        ],
                    }
                )
            return _response({"count": 3009, "next": None, "results": []})

    monkeypatch.setattr("app.sources.aides_territoires.httpx.post", post)
    monkeypatch.setattr("app.sources.aides_territoires.httpx.Client", Client)
    rows = list(AidesTerritoiresSource().fetch(date(2026, 11, 1), load_vertical()))
    assert len(rows) == 1
    assert rows[0]["id"] == 165655
    assert "contact" not in rows[0]
    assert any(call.get("text") == "éolien en mer" for call in calls)

    def ignored(self, url, params=None):
        return _response({"count": 3009, "next": None, "results": []})

    Client.get = ignored
    with pytest.raises(RuntimeError):
        list(AidesTerritoiresSource().fetch(date(2026, 11, 1), load_vertical()))
