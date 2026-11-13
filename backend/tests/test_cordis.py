"""Adaptador de CORDIS. Las filas de tests/fixtures/cordis/rows.json salen del volcado del 11 nov 2026."""

import csv
import io
import json
import zipfile
from pathlib import Path

from app.partners.cordis import content_hash, country_iso2, parse_zip
from app.vertical import load_vertical

FIXTURE = Path(__file__).parent / "fixtures" / "cordis" / "rows.json"
_PERSONAL = ("street", "postCode", "city", "geolocation", "vatNumber", "contactForm", "organizationURL")


def _zip(bundle: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, rows in (
            ("project.csv", bundle["projects"]),
            ("topics.csv", bundle["topics"]),
            ("organization.csv", bundle["orgs"]),
        ):
            text = io.StringIO()
            writer = csv.DictWriter(text, fieldnames=list(rows[0]), delimiter=";", quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(rows)
            archive.writestr(name, text.getvalue().encode("utf-8"))
    return buffer.getvalue()


def _parsed(programme: str):
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))[programme]
    source = "cordis-h2020" if programme == "h2020" else "cordis-horizon-europe"
    programme_id = "h2020" if programme == "h2020" else "horizon-europe"
    return parse_zip(
        _zip(bundle),
        source_id=source,
        programme_id=programme_id,
        vertical=load_vertical("blue-economy"),
    )


def test_horizon_keeps_the_topic_projects_and_drops_personal_fields():
    parsed = _parsed("horizon-europe")
    by_acronym = {row["acronym"]: row for row in parsed["projects"]}
    assert set(by_acronym) == {"BLADE2CIRC", "EOLIAN"}
    eolian = by_acronym["EOLIAN"]
    assert eolian["cordis_id"] == "101147532"
    assert eolian["url"] == "https://cordis.europa.eu/project/id/101147532"
    assert eolian["programme_id"] == "horizon-europe"
    assert "offshore-wind" in eolian["subsectors"]
    assert "HORIZON-CL5-2023-D3-02-15" in eolian["topics"]
    assert eolian["topic_title"].startswith("Critical technologies")
    assert eolian["end_year"] == 2027
    blob = json.dumps(parsed)
    for field in _PERSONAL:
        assert field not in blob
    countries = {row["country"] for row in parsed["orgs"]}
    assert "GB" in countries
    assert "UK" not in countries


def test_h2020_drops_terminated_projects_leavers_and_duplicate_rows():
    parsed = _parsed("h2020")
    acronyms = {row["acronym"] for row in parsed["projects"]}
    assert "WETFEET" in acronyms
    assert "DEMOGRAVI3" not in acronyms  # status TERMINATED
    assert "AdvancedStarForm" not in acronyms
    wetfeet = next(row for row in parsed["projects"] if row["acronym"] == "WETFEET")
    assert "ocean-energy" in wetfeet["subsectors"]
    assert wetfeet["url"] == "https://cordis.europa.eu/project/id/641334"
    kongsberg = [
        row for row in parsed["participations"]
        if row["org_id"] == "999444351"
    ]
    assert len(kongsberg) == 1
    assert kongsberg[0]["role"] == "participant"
    names = {row["name"] for row in parsed["orgs"]}
    assert "DCP DUTCH CARGO PURCHASE BV" not in names  # solo la fila de baja


def test_duplicate_roles_keep_the_coordinator():
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))["horizon-europe"]
    participant = next(row for row in bundle["orgs"] if row["role"] == "participant")
    coordinator = dict(participant)
    coordinator["role"] = "coordinator"
    coordinator["order"] = "1"
    coordinator["endOfParticipation"] = "false"
    bundle["orgs"].append(coordinator)
    parsed = parse_zip(
        _zip(bundle),
        source_id="cordis-horizon-europe",
        programme_id="horizon-europe",
        vertical=load_vertical("blue-economy"),
    )
    rows = [
        row for row in parsed["participations"]
        if row["org_id"] == participant["organisationID"]
        and row["project_id"].endswith(participant["projectID"])
    ]
    assert len(rows) == 1
    assert rows[0]["role"] == "coordinator"


def test_country_codes_and_a_stable_hash():
    assert country_iso2("UK") == "GB"
    assert country_iso2("EL") == "GR"
    assert country_iso2("") is None
    assert country_iso2("ZZZ") is None
    parsed = _parsed("h2020")
    assert content_hash(parsed) == content_hash(parsed)


def test_a_zip_without_the_project_file_fails_alone():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "no csv")
    try:
        parse_zip(buffer.getvalue(), source_id="cordis-h2020", programme_id="h2020", vertical=load_vertical())
    except ValueError as exc:
        assert "project.csv" in str(exc)
    else:
        raise AssertionError("tenía que fallar")


def test_the_job_does_not_rewrite_an_unchanged_dump(tmp_path):
    from app.jobs.cordis import run
    from app.store import FileStore

    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))["h2020"]
    path = tmp_path / "h2020.zip"
    path.write_bytes(_zip(bundle))
    store = FileStore(tmp_path / "opportunities.json")
    calls = []
    replace = store.replace_cordis

    def wrapped(*args, **kwargs):
        calls.append(1)
        return replace(*args, **kwargs)

    store.replace_cordis = wrapped
    assert run("cordis-h2020", file=path, store=store) == 0
    assert run("cordis-h2020", file=path, store=store) == 0
    assert calls == [1]
    assert store.cordis_participations()


def test_one_dump_failing_does_not_stop_the_other(tmp_path, monkeypatch):
    from app.jobs import cordis as job
    from app.store import FileStore

    he = _zip(json.loads(FIXTURE.read_text(encoding="utf-8"))["horizon-europe"])

    def fetch(url, **_kwargs):
        if "h2020" in url:
            raise RuntimeError("zip roto")
        return he, {"etag": "e", "last-modified": "Tue, 10 Nov 2026 13:11:43 GMT"}

    monkeypatch.setattr(job, "fetch_zip", fetch)
    store = FileStore(tmp_path / "opportunities.json")
    assert job.run(store=store) == 1
    acronyms = {row["acronym"] for row in store.cordis_participations()}
    assert "EOLIAN" in acronyms
    assert "cordis-h2020" not in store.track_record_sources()

