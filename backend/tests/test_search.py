from datetime import UTC, datetime

from app.models.opportunity import Opportunity
from app.search.query import SearchFilters, match_reason, search_opportunities, suggest_relaxation


def _item(title: str, **kwargs) -> Opportunity:
    base = {
        "id": title,
        "source_id": "t",
        "external_id": title,
        "url": "https://example.test/" + title,
        "title": title,
        "deadline_at": datetime(2026, 12, 1, tzinfo=UTC),
    }
    base.update(kwargs)
    return Opportunity(**base)


def test_unknown_subsector_stays_visible():
    known = _item("offshore wind farm", subsectors=["offshore-wind"])
    unknown = _item("untitled call")
    found = search_opportunities(
        [known, unknown],
        SearchFilters(subsector=["offshore-wind"], exclude_unknown=False),
        today=__import__("datetime").date(2026, 11, 11),
    )
    ids = {item.id for item in found["items"]}
    assert known.id in ids
    assert unknown.id in ids


def test_exclude_unknown_hides_blank_subsector():
    known = _item("offshore wind farm", subsectors=["offshore-wind"])
    unknown = _item("untitled call")
    found = search_opportunities(
        [known, unknown],
        SearchFilters(subsector=["offshore-wind"], exclude_unknown=True),
        today=__import__("datetime").date(2026, 11, 11),
    )
    ids = {item.id for item in found["items"]}
    assert ids == {known.id}


def test_awards_are_hidden():
    from app.models.opportunity import OpportunityType

    award = _item("award", type=OpportunityType.award)
    found = search_opportunities([award], SearchFilters(), today=__import__("datetime").date(2026, 11, 11))
    assert found["total"] == 0


def test_deadline_buckets_are_exclusive_and_closing_soon_is_sixty_days():
    today = __import__("datetime").date(2026, 11, 11)
    closed = _item("past", deadline_at=datetime(2026, 9, 5, tzinfo=UTC))
    soon = _item("soon", deadline_at=datetime(2026, 12, 15, tzinfo=UTC))
    later = _item("later", deadline_at=datetime(2027, 3, 1, tzinfo=UTC))
    edge = _item("edge", deadline_at=datetime(2027, 1, 10, tzinfo=UTC))  # justo 60 días
    found = search_opportunities(
        [closed, soon, later, edge],
        SearchFilters(deadline=["closing_soon"]),
        today=today,
    )
    assert {item.id for item in found["items"]} == {"soon", "edge"}
    assert found["counts"]["deadline"] == {"closed": 1, "closing_soon": 2, "open": 1}
    only_open = search_opportunities(
        [closed, soon, later, edge],
        SearchFilters(deadline=["open"]),
        today=today,
    )
    assert {item.id for item in only_open["items"]} == {"later"}


def test_kind_counts_ignore_the_selected_tab_and_follow_the_query():
    from app.models.opportunity import OpportunityKind

    grant = _item("offshore wind grant", kind=OpportunityKind.grant)
    tender = _item("offshore wind tender", kind=OpportunityKind.tender)
    other = _item("harbour dredging", kind=OpportunityKind.tender)
    found = search_opportunities(
        [grant, tender, other],
        SearchFilters(q="wind", kind=["grant"]),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert found["total"] == 1
    assert found["counts"]["all"] == 2
    assert found["counts"]["kind"] == {"grant": 1, "tender": 1}


def test_country_filter_keeps_only_calls_in_that_country():
    spain = _item("Puerto de Vigo", country="ES")
    europe = _item("Horizon topic")
    france = _item("Câble", country="FR")
    found = search_opportunities(
        [spain, europe, france],
        SearchFilters(country=["ES", "FR"]),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert {item.id for item in found["items"]} == {spain.id, france.id}
    codes = {row["value"] for row in found["facets"]["country"]}
    assert codes == {"ES", "FR"}
    assert found["facets"]["country_missing"] == 1
    missing = search_opportunities(
        [spain, europe, france],
        SearchFilters(country="uncategorized"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert [item.id for item in missing["items"]] == [europe.id]


def test_search_ranks_partial_words_and_ignores_case_and_accents():
    accented = _item("Parque eólica marina", description="convocatoria")
    only_wind = _item("OFFSHORE WIND")
    landstrom = _item("Landstromanlage", subsectors=["green-ports"], description="Hafen")
    found = search_opportunities(
        [accented, only_wind, landstrom],
        SearchFilters(q="eolica"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert {item.id for item in found["items"]} == {accented.id}
    masculine = search_opportunities(
        [accented, only_wind],
        SearchFilters(q="eolico"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert {item.id for item in masculine["items"]} == {accented.id}
    caps = search_opportunities(
        [only_wind],
        SearchFilters(q="wind"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert caps["total"] == 1
    plural = search_opportunities(
        [_item("Export cable"), _item("Harbour office")],
        SearchFilters(q="cables"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert {item.id for item in plural["items"]} == {"Export cable"}
    prefix = search_opportunities(
        [_item("Efficient decommissioning of turbines"), _item("Harbour office")],
        SearchFilters(q="decomm"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert {item.id for item in prefix["items"]} == {"Efficient decommissioning of turbines"}
    both = _item("Portimao OPS")
    only_ops = _item("OPS somewhere else")
    ranked = search_opportunities(
        [only_ops, both],
        SearchFilters(q="portimao ops"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert [item.id for item in ranked["items"]] == [both.id]
    shore = search_opportunities(
        [landstrom],
        SearchFilters(q="shore power"),
        today=__import__("datetime").date(2026, 11, 11),
    )
    assert shore["total"] == 1


def test_a_known_phrase_stays_together():
    day = __import__("datetime").date(2026, 11, 11)
    north_sea = _item("Offshore wind in the North Sea")
    tagged = _item("Havvind udbud", sea_basins=["north_sea"], subsectors=["offshore-wind"])
    only_wind = _item("Harbour wind load study")
    split = _item("North harbour and a sea lane", description="Offshore work and a wind reading")
    pasted = "North Sea I, Mid, Offshore Wind Farm"
    found = search_opportunities(
        [only_wind, split, north_sea, tagged],
        SearchFilters(q="north sea"),
        today=day,
    )
    assert {item.id for item in found["items"]} == {north_sea.id, tagged.id}
    whole = search_opportunities(
        [only_wind, split, north_sea, tagged],
        SearchFilters(q=pasted),
        today=day,
    )
    assert {item.id for item in whole["items"]} == {north_sea.id, tagged.id}
    assert match_reason(north_sea, "north sea") == "Matches north sea"
    assert match_reason(tagged, "north sea") == "Classified in north_sea"


def test_empty_search_suggests_a_filter_to_drop():
    items = [_item("offshore wind", subsectors=["offshore-wind"])]
    filters = SearchFilters(subsector=["ocean-energy"], exclude_unknown=True)
    assert search_opportunities(items, filters, today=__import__("datetime").date(2026, 11, 11))["total"] == 0
    hint = suggest_relaxation(items, filters, today=__import__("datetime").date(2026, 11, 11))
    assert hint and "match if you drop" in hint
