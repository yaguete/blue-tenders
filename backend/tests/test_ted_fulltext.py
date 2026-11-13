"""Búsqueda por texto completo en TED y cómo viaja su resultado por el pipeline."""

import os
from datetime import date, timedelta

import httpx
import pytest

from app.enrich.classify import classify_rules
from app.pipeline.run import prefilter
from app.sources import ted
from app.sources.base import SOURCE_SUBSECTORS
from app.sources.ted import (
    FIELDS,
    SEARCH_URL,
    TedSource,
    build_fulltext_query,
    fulltext_clause,
)
from app.vertical import Subsector, Vertical, load_vertical


def test_phrase_keyword_becomes_exact_phrase():
    assert fulltext_clause("offshore substation") == 'FT ~ "offshore substation"'
    # TED ignora acentos y guiones; se le manda ya normalizado.
    assert fulltext_clause("câble sous-marin") == 'FT ~ "cable sous marin"'
    assert fulltext_clause("Eólica Marina") == 'FT ~ "eolica marina"'


def test_single_word_wildcard_goes_outside_quotes():
    # Dentro de las comillas el comodín no se expande.
    assert fulltext_clause("landstrom*") == "FT ~ landstrom*"


def test_multi_word_wildcard_is_not_searched_in_full_text():
    # TED solo sabe hacerlo con AND, que casa con las palabras en cualquier parte del anuncio.
    assert fulltext_clause("eólic* offshore") is None
    assert fulltext_clause("emissionsfrei* schiff*") is None


def test_vertical_never_sends_a_loose_and_to_ted():
    v = load_vertical("blue-economy")
    for sub in v.active_subsectors:
        query = build_fulltext_query(date(2026, 11, 1), sub.keywords)
        assert query and " AND publication-date" in query
        assert " AND " not in query.rsplit(" AND publication-date", 1)[0], sub.id
    wind = build_fulltext_query(date(2026, 11, 1), v.active_subsectors[0].keywords)
    assert 'FT ~ "offshore wind"' in wind  # la frase principal no puede quedarse solo en local


def test_short_acronym_is_not_searched_in_full_text():
    assert fulltext_clause("OPS") is None
    assert fulltext_clause("CENAQ") == 'FT ~ "cenaq"'


def test_keyword_cannot_break_out_of_the_query():
    clause = fulltext_clause('x" OR publication-date>=19000101 OR FT ~ "y')
    assert clause.count('"') == 2
    assert ">" not in clause and "=" not in clause


def test_each_term_gets_its_own_clause():
    q = build_fulltext_query(date(2026, 11, 1), ["shore power", "landstrom*", "OPS", "shore power"])
    assert q == '(FT ~ "shore power" OR FT ~ landstrom*) AND publication-date>=20261101'
    # `FT ~ ("a" OR "b")` devuelve 0 resultados sin dar error.
    assert 'FT ~ ("' not in q


def test_no_usable_keywords_means_no_query():
    assert build_fulltext_query(date(2026, 11, 1), ["OPS"]) is None
    assert build_fulltext_query(date(2026, 11, 1), []) is None


def _vertical(cpv: list[str]) -> Vertical:
    return Vertical(
        id="v",
        name="V",
        cpv=cpv,
        subsectors=[
            Subsector(id="wind", name="Wind", enabled=True, keywords=["offshore wind"]),
            Subsector(id="cables", name="Cables", enabled=True, keywords=["subsea cable"]),
            Subsector(id="off", name="Off", enabled=False, keywords=["fishing"]),
        ],
    )


def _fake_pages(results: dict[str, list[str]]):
    queries: list[str] = []

    def pages(_client, query: str):
        queries.append(query)
        key = next(k for k in results if k in query)
        return iter({"publication-number": n} for n in results[key])

    return pages, queries


def test_fetch_merges_full_text_and_cpv(monkeypatch):
    pages, queries = _fake_pages(
        {"offshore wind": ["1", "2"], "subsea cable": ["2", "3"], "classification-cpv": ["3", "4"]}
    )
    monkeypatch.setattr(ted, "_pages", pages)

    out = list(TedSource().fetch(date(2026, 11, 1), _vertical(["45240000"])))

    by_number = {n["publication-number"]: n for n in out}
    assert sorted(by_number) == ["1", "2", "3", "4"]  # sin repetidos
    assert by_number["1"][SOURCE_SUBSECTORS] == ["wind"]
    assert by_number["2"][SOURCE_SUBSECTORS] == ["wind", "cables"]
    assert by_number["3"][SOURCE_SUBSECTORS] == ["cables"]  # conserva la marca aunque salga por CPV
    assert SOURCE_SUBSECTORS not in by_number["4"]
    assert len(queries) == 3 and not any(
        "fishing" in q for q in queries
    )  # solo subsectores activos


def test_fetch_without_cpv_uses_full_text_only(monkeypatch):
    pages, queries = _fake_pages({"offshore wind": ["1"], "subsea cable": []})
    monkeypatch.setattr(ted, "_pages", pages)
    out = list(TedSource().fetch(date(2026, 11, 1), _vertical([])))
    assert [n["publication-number"] for n in out] == ["1"]
    assert not any("classification-cpv" in q for q in queries)


def test_fetch_refuses_to_query_all_of_ted():
    empty = Vertical(id="v", name="V", subsectors=[])
    with pytest.raises(ValueError):
        list(TedSource().fetch(date(2026, 11, 1), empty))


def _notice(**extra) -> dict:
    # El título no nombra el sector: es el caso que el texto completo rescata.
    return {
        "publication-number": "9-2026",
        "notice-title": {"eng": "Netherlands – Geophysical consultancy services – Benthic survey"},
        **extra,
    }


def test_prefilter_keeps_what_the_source_found():
    v = load_vertical("blue-economy")
    src = TedSource()
    plain = src.to_tender(_notice())
    found = src.to_tender(_notice(**{SOURCE_SUBSECTORS: ["offshore-wind"]}))
    assert prefilter([plain], v) == []
    assert prefilter([found], v) == [found]


def test_classifier_uses_what_the_source_found():
    v = load_vertical("blue-economy")
    src = TedSource()
    plain = classify_rules(src.to_tender(_notice()), v)
    found = classify_rules(src.to_tender(_notice(**{SOURCE_SUBSECTORS: ["offshore-wind"]})), v)
    assert plain.subsectors == []
    assert found.subsectors == ["offshore-wind"]


def test_classifier_ignores_unknown_subsectors_from_the_source():
    v = load_vertical("blue-economy")
    opp = classify_rules(TedSource().to_tender(_notice(**{SOURCE_SUBSECTORS: ["no-existe"]})), v)
    assert opp.subsectors == []


@pytest.mark.skipif(not os.environ.get("TED_LIVE"), reason="llama a la API real; usa TED_LIVE=1")
def test_live_api_accepts_every_full_text_query():
    v = load_vertical("blue-economy")
    since = date.today() - timedelta(days=90)
    total = 0
    for sub in v.active_subsectors:
        query = build_fulltext_query(since, sub.keywords)
        r = httpx.post(
            SEARCH_URL,
            json={"query": query, "fields": FIELDS, "limit": 1, "scope": "ALL"},
            timeout=60,
        )
        assert r.status_code == 200, f"{sub.id}: {r.text[:500]}"
        total += r.json().get("totalNoticeCount", 0)
    # Si la sintaxis falla en silencio, TED devuelve 0 con un 200.
    assert total > 0
