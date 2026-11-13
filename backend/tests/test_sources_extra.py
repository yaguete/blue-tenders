import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.models.opportunity import Opportunity, OpportunityKind
from app.sources.bdns import BdnsSource
from app.sources.curated import CuratedSource
from app.sources.eu_ft import EuFtSource, _fill_detail
from app.sources.placsp import PlacspSource, _cpv_ok, feed_root
from app.sources.terms import search_pairs
from app.vertical import load_vertical

FIXTURES = Path(__file__).parent / "fixtures"


def test_eu_ft_maps_a_topic_without_inventing_a_second_deadline():
    raw = json.loads((FIXTURES / "eu_ft" / "topic.json").read_text())
    item = EuFtSource().to_tender(raw)
    assert item.external_id == "HORIZON-CL5-2026-D3-01-01"
    assert item.programme_id == "horizon-europe"
    assert item.type_of_action == "RIA"
    assert item.budget_total_eur == 4_000_000
    assert item.deadline_at is not None
    assert item.deadline_at.hour == 17
    assert len(item.deadlines) == 1


def test_placsp_html_error_is_not_parsed_as_an_empty_feed():
    html = (FIXTURES / "placsp" / "html_error.html").read_bytes()
    with pytest.raises(RuntimeError, match="HTML"):
        feed_root(html)


def test_placsp_cpv_keeps_a_real_energy_code_and_drops_the_rest():
    vertical = load_vertical()
    entry = ET.fromstring((FIXTURES / "placsp" / "cpv_fragment.xml").read_text())
    assert _cpv_ok(entry, vertical.cpv)
    noise = ET.fromstring(
        "<entry><ItemClassificationCode>92000000</ItemClassificationCode></entry>"
    )
    assert not _cpv_ok(noise, vertical.cpv)
    bare = ET.fromstring("<entry><ContractFolderID>sin-cpv</ContractFolderID></entry>")
    assert _cpv_ok(bare, vertical.cpv)


def test_bdns_searches_the_terms_configured_for_it():
    pairs = search_pairs(load_vertical(), "bdns")
    assert ("offshore-wind", "eólico") in pairs
    assert ("green-ports", "puerto") in pairs
    assert all("marina" not in term for _, term in pairs)
    row = json.loads((FIXTURES / "bdns" / "search.json").read_text())["content"][0]
    item = BdnsSource().to_tender(row)
    assert item.external_id == "936328"
    assert item.published_at is not None
    assert item.published_at.isoformat() == "2026-10-20"


def test_placsp_reads_codice_fields():
    xml = (FIXTURES / "placsp" / "entry.xml").read_text()
    item = PlacspSource().to_tender({"xml": xml})
    assert item.country == "ES"
    assert item.buyer is not None
    assert item.buyer.name == "Autoridad Portuaria de Vigo"
    assert "buques" in item.title
    assert item.budget is not None
    assert item.budget.amount_eur == 1_200_000
    assert item.nuts == ["ES11"]


def test_bdns_loan_does_not_parse_a_prose_deadline():
    item = BdnsSource().to_tender(
        {
            "codigoBDNS": "123",
            "titulo": "Ayuda a la eólica marina",
            "instrumentos": ["Préstamo"],
            "fechaPublicacion": "02/11/2026",
            "plazoTexto": "un mes desde la publicación",
            "importeTotal": 50000,
            "organo": "IDAE",
        }
    )
    assert item.kind == OpportunityKind.loan
    assert item.deadline_at is None
    assert item.published_at is not None
    assert item.published_at.isoformat() == "2026-11-02"


def test_eu_ft_reads_a_budget_stored_as_a_list_of_actions():
    raw = {
        "metadata": {
            "identifier": ["HORIZON-CL5-2026-D3-01-01"],
            "title": ["Offshore wind"],
            "type": ["1"],
            "budgetOverview": [
                json.dumps(
                    {
                        "budgetTopicActionMap": {
                            "HORIZON-CL5-2026-D3-01-01": [
                                {
                                    "action": "HORIZON-RIA",
                                    "budgetYearMap": [{"budget": 4000000}],
                                    "minContribution": 2000000,
                                    "maxContribution": 4000000,
                                    "expectedGrants": 2,
                                }
                            ]
                        }
                    }
                )
            ],
        }
    }
    item = EuFtSource().to_tender(raw)
    assert item.budget_total_eur == 4_000_000
    assert item.amount_min_eur == 2_000_000
    assert item.amount_max_eur == 4_000_000
    assert any(fact.field == "expected_grants" and fact.value == 2 for fact in item.facts)


def test_eu_ft_keeps_two_deadlines_and_a_cascade_apart_from_a_grant():
    from app.enrich.rules import apply_programme_rules
    from app.models.opportunity import NoticeKind

    two = {
        "metadata": {
            "identifier": ["HORIZON-CL5-2026-02"],
            "title": ["Two stage offshore wind"],
            "type": ["1"],
            "typesOfAction": ["HORIZON-RIA"],
            "frameworkProgramme": ["Horizon Europe"],
            "deadlineDate": ["2026-04-01T17:00:00+0000", "2026-09-01T17:00:00+0000"],
            "descriptionByte": ["<p>Offshore wind demonstration.</p>"],
        }
    }
    item = apply_programme_rules(EuFtSource().to_tender(two))
    assert item.deadline_model.value == "two_stage"
    assert item.deadline_at.month == 4
    assert len(item.deadlines) == 2
    assert item.description == "Offshore wind demonstration."
    assert any(doc.kind == "topic_text" and doc.access == "inline" for doc in item.documents)
    assert item.consortium_min_partners == 3

    forthcoming = {
        "metadata": {
            "identifier": ["HORIZON-CL5-2027-01"],
            "title": ["Forthcoming"],
            "type": ["1"],
            "status": ["31094501"],
            "deadlineDate": ["2027-02-01T00:00:00+0000"],
        }
    }
    upcoming = EuFtSource().to_tender(forthcoming)
    assert any(fact.field == "deadline_time" and fact.value == "unknown" for fact in upcoming.facts)

    shared = "HORIZON-PARENT"
    first = EuFtSource().to_tender(
        {"metadata": {"type": ["8"], "identifier": [shared], "callccm2Id": ["A"], "callTitle": ["Cascade A"]}}
    )
    second = EuFtSource().to_tender(
        {"metadata": {"type": ["8"], "identifier": [shared], "callccm2Id": ["B"], "callTitle": ["Cascade B"]}}
    )
    assert first.id != second.id
    assert first.notice == NoticeKind.cascade
    assert first.kind.value == "grant"
    aid = EuFtSource().to_tender(
        {"metadata": {"type": ["2"], "identifier": ["EuropeAid-1"], "title": ["External grant"]}}
    )
    assert aid.kind.value == "grant"
    assert aid.notice == NoticeKind.call_for_proposals


def test_placsp_uses_the_submission_deadline_not_the_contract_end():
    xml = """<entry>
      <ContractFolderID>exp-1</ContractFolderID>
      <ProcurementProject><Name>Cable submarino</Name></ProcurementProject>
      <EndDate>2027-01-01</EndDate>
      <TenderSubmissionDeadlinePeriod>
        <EndDate>2026-12-02</EndDate>
        <EndTime>12:30:00</EndTime>
      </TenderSubmissionDeadlinePeriod>
    </entry>"""
    item = PlacspSource().to_tender({"xml": xml})
    assert item.deadline_at is not None
    assert item.deadline_at.day == 2
    assert item.deadline_at.hour == 12


def test_bdns_detail_keeps_the_hour_and_a_filter_must_shrink_the_total():
    import pytest

    from app.sources.bdns import filters_bite

    item = BdnsSource().to_tender(
        {
            "numeroConvocatoria": "877815",
            "descripcion": "Puertos para eólica marina",
            "fechaFinSolicitud": "03/03/2026",
            "textFin": "Hasta las 12:00 horas del mediodía del 3 de marzo de 2026",
            "presupuestoTotal": 212000000,
            "tiposBeneficiarios": ["Empresa"],
            "fondos": ["EMFAF"],
            "organo": "IDAE",
        }
    )
    assert item.external_id == "877815"
    assert item.deadline_at is not None
    assert item.deadline_at.hour == 12
    assert item.budget_total_eur == 212000000
    assert any(fact.field == "fund" for fact in item.facts)
    with pytest.raises(RuntimeError):
        filters_bite(100, 100)


def test_topic_detail_keeps_expected_outcome_and_conditions():
    from app.sources.eu_ft import topic_text_from_detail

    text = topic_text_from_detail(
        {
            "TopicDetails": {
                "description": '<p class="topicdescriptionkind">Expected Outcome:</p><p>Longer lifetime at sea.</p>',
                "conditions": "<h4>General conditions</h4><p>Deadline 5 September 2023 17:00.</p>",
            }
        }
    )
    assert "Expected Outcome" in text
    assert "Longer lifetime at sea." in text
    assert "General conditions" in text
    assert "17:00" in text


def test_eu_ft_keeps_topic_sections_and_skips_general_annexes():
    raw = {
        "metadata": {
            "identifier": ["HORIZON-CL5-2026-D3-01-09"],
            "title": ["Floating wind"],
            "type": ["1"],
            "descriptionByte": [
                "<h2>Expected outcome</h2><p>A demonstrated turbine.</p><h2>Scope</h2><p>Offshore floating wind.</p>"
            ],
            "topicConditions": [
                "See https://ec.europa.eu/docs/wp-13-general-annexes_horizon-2026-2027_en.pdf"
            ],
        }
    }
    item = EuFtSource().to_tender(raw)
    assert "## Expected outcome" in item.description
    assert "## Scope" in item.description
    assert all("general-annex" not in doc.url for doc in item.documents)
    assert any(doc.access == "inline" for doc in item.documents)


def test_placsp_keeps_the_specifications_linked_in_the_entry():
    xml = """<entry>
      <ContractFolderID>exp-9</ContractFolderID>
      <link href="https://contrataciondelestado.es/expediente/exp-9"/>
      <ProcurementProject><Name>Cable submarino</Name></ProcurementProject>
      <LegalDocumentReference>
        <DocumentTypeCode>DOC_PPT</DocumentTypeCode>
        <URI>https://contrataciondelestado.es/pliego/ppt.pdf</URI>
      </LegalDocumentReference>
    </entry>"""
    item = PlacspSource().to_tender({"xml": xml})
    pliego = next(doc for doc in item.documents if doc.kind == "pliego")
    assert pliego.name == "Technical specifications"
    assert pliego.access == "fetch"


def test_bdns_reads_the_call_pdf_and_the_regulatory_bases():
    item = BdnsSource().to_tender(
        {
            "numeroConvocatoria": "877815",
            "descripcion": "Puertos para eólica marina",
            "documentos": [{"url": "https://www.infosubvenciones.es/bdnstrans/doc/877815.pdf", "nombre": "Convocatoria"}],
            "urlBasesReguladoras": "https://www.boe.es/boe/dias/2026/bases.pdf",
        }
    )
    kinds = {doc.kind for doc in item.documents}
    assert kinds == {"notice", "bases"}


def test_ted_keeps_buyer_documents_as_links_only():
    from app.sources.ted import TedSource

    item = TedSource().to_tender(
        {
            "publication-number": "1-2026",
            "notice-title": {"eng": "Offshore wind maintenance"},
            "official-language": "ENG",
            "links": {
                "pdf": {"ENG": "https://ted.europa.eu/en/notice/1-2026/pdf"},
                "html": {"ENG": "https://ted.europa.eu/en/notice/1-2026"},
            },
            "document-url-lot": {"eng": ["https://buyer.example/pliego"]},
        }
    )
    notice = next(doc for doc in item.documents if doc.kind == "notice")
    lot = next(doc for doc in item.documents if doc.kind == "tender_documents")
    assert notice.access == "fetch"
    assert lot.access == "link_only"
    assert lot.url == "https://buyer.example/pliego"


def test_curated_sbep_keeps_the_checked_quote():
    rows = list(CuratedSource().fetch(__import__("datetime").date(2026, 1, 1), None))
    item = CuratedSource().to_tender(rows[0])
    assert item.external_id == "SBEP-JTC-2026"
    assert item.facts[0].quote.startswith("Pre-proposal")
    assert item.deadline_at is not None
    assert item.deadline_at.day == 16
    assert any(doc.name == "Call (PDF)" and doc.url.endswith(".pdf") for doc in item.documents)


def _portal_topic(identifier: str, **meta) -> dict:
    base = {
        "identifier": [identifier],
        "title": ["Wave devices"],
        "type": ["1"],
        "callIdentifier": ["HORIZON-CL5-2023-D3-02"],
        "callTitle": ["Sustainable, secure and competitive energy supply"],
    }
    base.update(meta)
    return {"metadata": base}


_OVERVIEW = {
    "budgetTopicActionMap": {
        "1": [
            {
                "action": "HORIZON-CL5-2023-D3-02-1 - HORIZON-RIA",
                "budgetYearMap": {"2023": "1000000"},
                "expectedGrants": 1,
                "minContribution": 1000000,
                "maxContribution": 1000000,
            }
        ],
        "10": [
            {
                "action": "HORIZON-CL5-2023-D3-02-10 - HORIZON-RIA",
                "budgetYearMap": {"2023": "8000000"},
                "expectedGrants": 2,
                "minContribution": 4000000,
                "maxContribution": 4000000,
            }
        ],
    }
}


def _fact(item, field):
    return next(fact for fact in item.facts if fact.field == field)


def test_eu_ft_reads_a_budget_year_map_object_for_the_exact_topic():
    raw = _portal_topic("HORIZON-CL5-2023-D3-02-10", budgetOverview=[json.dumps(_OVERVIEW)])
    item = EuFtSource().to_tender(raw)
    assert item.budget_total_eur == 8_000_000
    assert item.amount_min_eur == 4_000_000
    assert item.amount_max_eur == 4_000_000
    assert item.call_id == "HORIZON-CL5-2023-D3-02"
    assert _fact(item, "call_title").value == "Sustainable, secure and competitive energy supply"
    assert _fact(item, "call_topics_count").value == 2
    assert _fact(item, "expected_grants").value == 2


def test_eu_ft_does_not_give_topic_1_the_budget_of_topic_10():
    raw = _portal_topic("HORIZON-CL5-2023-D3-02-1", budgetOverview=[json.dumps(_OVERVIEW)])
    item = EuFtSource().to_tender(raw)
    assert item.budget_total_eur == 1_000_000


def test_eu_ft_reads_proposal_counts_without_mixing_neighbouring_topics():
    infos = [
        {
            "content": (
                "<p>HORIZON-CL5-2023-D3-02-10&#xa0;(RIA-LS): 15 proposals</p>"
                "<p>HORIZON-CL5-2023-D3-02-01 (RIA): <a>16 proposals</a></p>"
                "<p>The submission session is now available for: HORIZON-CL5-2023-D3-02-10(HORIZON-RIA)</p>"
            )
        }
    ]
    ten = EuFtSource().to_tender(_portal_topic("HORIZON-CL5-2023-D3-02-10", latestInfos=infos))
    one = EuFtSource().to_tender(_portal_topic("HORIZON-CL5-2023-D3-02-01", latestInfos=infos))
    bare = EuFtSource().to_tender(_portal_topic("HORIZON-CL5-2023-D3-02-10"))
    assert _fact(ten, "proposals_submitted").value == 15
    assert "15 proposals" in _fact(ten, "proposals_submitted").quote
    assert _fact(one, "proposals_submitted").value == 16
    assert all(fact.field != "proposals_submitted" for fact in bare.facts)
    assert all(fact.field != "latest_info" for fact in ten.facts)


def test_eu_ft_detail_wrapped_in_topic_details_fills_text_budget_and_call():
    class Response:
        status_code = 200

        def json(self):
            return {
                "TopicDetails": {
                    "description": (
                        '<p class="topicdescriptionkind">Expected Outcome:</p><p>More energy from waves.</p>'
                    ),
                    "conditions": "<h4>General conditions</h4><p>See Annex A.</p>",
                    "budgetOverviewJSONItem": _OVERVIEW,
                    "callIdentifier": "HORIZON-CL5-2023-D3-02",
                    "callTitle": "Sustainable, secure and competitive energy supply",
                    "latestInfos": [
                        {"content": "<p>HORIZON-CL5-2023-D3-02-10 (RIA-LS): 15 proposals</p>"}
                    ],
                }
            }

    class Client:
        def get(self, url, timeout=20):
            del url, timeout
            return Response()

    row = {
        "metadata": {
            "identifier": ["HORIZON-CL5-2023-D3-02-10"],
            "title": ["Wave devices"],
            "type": ["1"],
        }
    }
    _fill_detail(Client(), row)
    item = EuFtSource().to_tender(row)
    assert "More energy from waves" in (item.description or "")
    assert "Annex A" in (item.description or "")
    assert item.budget_total_eur == 8_000_000
    assert item.call_id == "HORIZON-CL5-2023-D3-02"
    assert _fact(item, "proposals_submitted").value == 15


def test_call_title_changes_the_portal_hash_and_nothing_else():
    item = EuFtSource().to_tender(_portal_topic("HORIZON-CL5-2023-D3-02-10"))
    dumped = item.model_dump()
    dumped["facts"] = [fact for fact in dumped["facts"] if fact["field"] != "call_title"]
    dumped["content_hash"] = None
    without = Opportunity(**dumped)
    assert item.content_hash != without.content_hash
    again = Opportunity(**{**item.model_dump(), "content_hash": None})
    assert again.content_hash == item.content_hash
