"""Adaptador de TED. Los anuncios de `fixtures/ted/search_page.json` son reales (11 nov 2026)."""

import json
import os
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.models.tender import OpportunityType
from app.sources.ted import FIELDS, SEARCH_URL, TedSource, build_query, search
from app.vertical import load_vertical

FIXTURE = Path(__file__).parent / "fixtures" / "ted" / "search_page.json"


@pytest.fixture
def notices() -> dict[str, dict]:
    page = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {n["publication-number"]: n for n in page["notices"]}


def test_query_separates_cpv_with_spaces():
    q = build_query(date(2026, 11, 1), ["45251160", "31682000"])
    assert q == "classification-cpv IN (45251160 31682000) AND publication-date>=20261101"
    assert " OR " not in q  # TED responde 400 a `IN (a OR b)`


def test_query_rejects_empty_or_malformed_cpv():
    with pytest.raises(ValueError):
        build_query(date(2026, 11, 1), [])
    with pytest.raises(ValueError):
        build_query(date(2026, 11, 1), ["45251160) OR (1=1"])


def test_fields_are_listed_explicitly():
    assert "*" not in FIELDS  # TED responde 400 al comodín


def test_contract_notice_is_mapped(notices):
    t = TedSource().to_tender(notices["760071-2026"])

    assert t.external_id == "760071-2026"
    assert t.type == OpportunityType.tender
    assert t.title == "Varvsöversyn vägfärja VF322/Göta"  # original, en sueco
    assert t.title_en and t.title_en.startswith("Sweden")  # el inglés viene de la fuente
    assert t.language == "sv"
    assert t.buyer.name == "Trafikverket Myndighet"
    assert t.buyer.country == "SE"
    assert t.country == "SE"
    assert t.region == "SE110"
    assert t.cpv == ["50240000", "50200000", "50241100"]  # sin repetidos
    assert t.published_at == date(2026, 11, 2)
    assert t.deadline_at == datetime(2026, 11, 29, 23, 59, tzinfo=timezone(timedelta(hours=1)))
    assert t.budget.amount == 4_000_000
    assert t.budget.currency == "SEK"
    assert t.budget.amount_eur is None  # no se convierte sin tipo de cambio
    assert t.url == "https://ted.europa.eu/en/notice/-/detail/760071-2026"
    assert t.documents[0].url.endswith("/760071-2026/pdf")


def test_award_notices_are_typed_as_award(notices):
    src = TedSource()
    award = src.to_tender(notices["756943-2026"])
    modification = src.to_tender(notices["762033-2026"])

    assert award.type == OpportunityType.award
    assert modification.type == OpportunityType.award
    assert award.language == "es"
    assert award.country == "ES"
    assert award.deadline_at is None  # una adjudicación no tiene plazo: no se inventa
    assert award.budget is None


def test_prior_information_notice_and_date_only_deadline():
    t = TedSource().to_tender(
        {
            "publication-number": "1-2026",
            "notice-type": "pin-only",
            "official-language": ["ENG"],
            "notice-title": {"eng": "Ireland – Shore power"},
            "buyer-country": ["IRL"],
            "deadline-receipt-tender-date-lot": ["2026-12-10+01:00", "2026-12-05Z"],
        }
    )
    assert t.type == OpportunityType.prior_information_notice
    assert t.country == "IE"
    # Sin hora en la fuente: inicio del día del lote más temprano, nunca más tarde.
    assert t.deadline_at == datetime(2026, 12, 5, tzinfo=UTC)


def test_unknown_country_is_left_empty():
    t = TedSource().to_tender(
        {"publication-number": "2-2026", "notice-title": {"eng": "x"}, "buyer-country": ["ZZZ"]}
    )
    assert t.country is None


def test_notice_without_number_or_title_is_rejected():
    with pytest.raises(ValueError):
        TedSource().to_tender({"notice-title": {"eng": "x"}})
    with pytest.raises(ValueError):
        TedSource().to_tender({"publication-number": "3-2026"})


def _client(responses: list[httpx.Response]) -> tuple[httpx.Client, list[int]]:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return responses[min(len(calls), len(responses)) - 1]

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_search_retries_transient_failures():
    client, calls = _client(
        [
            httpx.Response(503),
            httpx.Response(200, content=b""),
            httpx.Response(200, json={"notices": []}),
        ]
    )
    assert search(client, {}, backoff=0) == {"notices": []}
    assert len(calls) == 3


def test_search_does_not_retry_a_bad_query():
    client, calls = _client([httpx.Response(400, json={"message": "unsupported value"})])
    with pytest.raises(RuntimeError, match="TED 400"):
        search(client, {}, backoff=0)
    assert len(calls) == 1


def test_search_gives_up_after_retries():
    client, calls = _client([httpx.Response(503)])
    with pytest.raises(RuntimeError, match="no responde"):
        search(client, {}, backoff=0)
    assert len(calls) == 3


@pytest.mark.skipif(not os.environ.get("TED_LIVE"), reason="llama a la API real; usa TED_LIVE=1")
def test_live_api_accepts_query_and_fields():
    v = load_vertical("blue-economy")
    payload = {
        "query": build_query(date.today() - timedelta(days=7), v.cpv),
        "fields": FIELDS,
        "limit": 1,
        "scope": "ALL",
        "paginationMode": "ITERATION",
    }
    r = httpx.post(SEARCH_URL, json=payload, timeout=30)
    assert r.status_code == 200, r.text[:500]
    assert "notices" in r.json()


def test_real_award_notices_keep_winners_without_inventing_an_amount():
    page = json.loads((FIXTURE.parent / "awards.json").read_text(encoding="utf-8"))
    notices = {notice["publication-number"]: notice for notice in page["notices"]}
    source = TedSource()

    deep = source.to_tender(notices["745518-2025"])
    winners = next(fact.value for fact in deep.facts if fact.field == "winners")
    assert winners[0]["name"] == "DeepOcean AS"
    assert winners[0]["country"] == "NO"
    assert winners[0]["size"] == "medium"
    assert winners[0]["id_hash"]
    assert not any(fact.field == "award_value_eur" for fact in deep.facts)

    cable = source.to_tender(notices["780925-2025"])
    winners = next(fact.value for fact in cable.facts if fact.field == "winners")
    assert [row["name"] for row in winners] == ["Prysmian Powerlink Srl", "Roda SpA", "Cebat SpA"]
    assert {row["country"] for row in winners} == {"IT"}
    assert all(row["id_hash"] is None for row in winners)
    assert not any(fact.field == "award_value_eur" for fact in cable.facts)

    sek = source.to_tender(notices["867003-2025"])
    winners = next(fact.value for fact in sek.facts if fact.field == "winners")
    assert winners[0]["name"] == "Festo AB"
    assert winners[0]["country"] == "SE"
    assert winners[0]["id_hash"] is None
    assert not any(fact.field == "award_value_eur" for fact in sek.facts)


def test_a_confidential_or_unknown_award_amount_stays_empty():
    unknown = TedSource().to_tender(
        {
            "publication-number": "9-2026",
            "notice-type": "can-standard",
            "notice-title": {"eng": "Cable"},
            "result-value-notice": "-1",
            "result-value-cur-notice": "EUR",
        }
    )
    assert not any(fact.field == "award_value_eur" for fact in unknown.facts)


def test_a_positive_eur_award_is_kept_and_changes_the_hash():
    awarded = TedSource().to_tender(
        {
            "publication-number": "8-2026",
            "notice-type": "can-standard",
            "notice-title": {"eng": "Cable"},
            "result-value-notice": "1250000",
            "result-value-cur-notice": "EUR",
            "winner-name": {"eng": ["Grid Co"]},
            "winner-country": ["NOR"],
            "winner-identifier": ["980722805"],
            "winner-size": ["medium"],
        }
    )
    amount = next(fact.value for fact in awarded.facts if fact.field == "award_value_eur")
    assert amount == 1_250_000
    assert not any(fact.field == "contract_end_at" for fact in awarded.facts)
    bare = TedSource().to_tender(
        {"publication-number": "8-2026", "notice-type": "can-standard", "notice-title": {"eng": "Cable"}}
    )
    assert bare.content_hash != awarded.content_hash


def test_contract_end_is_kept_only_when_every_lot_agrees():
    agreed = TedSource().to_tender(
        {
            "publication-number": "7-2026",
            "notice-type": "can-standard",
            "notice-title": {"eng": "Cable"},
            "contract-duration-end-date-lot": ["2028-10-22+03:00", "2028-10-22+02:00"],
        }
    )
    assert next(fact.value for fact in agreed.facts if fact.field == "contract_end_at") == "2028-10-22"
    split = TedSource().to_tender(
        {
            "publication-number": "6-2026",
            "notice-type": "can-standard",
            "notice-title": {"eng": "Cable"},
            "contract-duration-end-date-lot": ["2028-10-22+03:00", "2029-01-01Z"],
        }
    )
    assert not any(fact.field == "contract_end_at" for fact in split.facts)
    bare = TedSource().to_tender(
        {"publication-number": "7-2026", "notice-type": "can-standard", "notice-title": {"eng": "Cable"}}
    )
    assert bare.content_hash != agreed.content_hash


def test_dedupe_keeps_the_call_and_its_award():
    from app.models.opportunity import NoticeKind, OpportunityType
    from app.pipeline.run import dedupe

    call = TedSource().to_tender(
        {
            "publication-number": "1-2026",
            "notice-type": "cn-standard",
            "notice-title": {"eng": "Shore power"},
            "procedure-identifier": "proc-1",
        }
    )
    award = TedSource().to_tender(
        {
            "publication-number": "2-2026",
            "notice-type": "can-standard",
            "notice-title": {"eng": "Shore power"},
            "procedure-identifier": "proc-1",
            "winner-name": {"eng": ["Port Co"]},
            "winner-country": ["PRT"],
        }
    )
    placsp = call.model_copy(update={"id": "placsp-1", "source_id": "placsp", "external_id": "1"})
    placsp.raw = {"procedure-identifier": "proc-1"}
    kept = dedupe([call, award, placsp])
    ids = {item.id for item in kept}
    assert call.id in ids
    assert award.id in ids
    assert placsp.id not in ids
    assert award.notice == NoticeKind.award_notice
    assert call.type == OpportunityType.tender
