from pathlib import Path

from app.models.opportunity import FactOrigin, NoticeKind
from app.sources.placsp import PlacspConsultasSource


def test_a_real_preliminary_consultation_is_a_pin_without_a_tender_deadline():
    xml = (Path(__file__).parent / "fixtures" / "placsp" / "consulta.xml").read_text(encoding="utf-8")
    item = PlacspConsultasSource().to_tender({"xml": xml})
    assert item.source_id == "placsp-consultas"
    assert item.external_id == "CP/14672/2026"
    assert item.notice == NoticeKind.pin
    assert item.deadline_at is None
    assert item.published_at is not None and item.published_at.isoformat() == "2026-11-12"
    assert item.country == "ES"
    assert item.buyer is not None and item.buyer.name.startswith("Consejería")
    assert "isConsPre=1" in item.url
    response = next(fact for fact in item.facts if fact.field == "response_by")
    assert response.origin == FactOrigin.source
    assert response.quote == "2026-12-30"
    assert response.value == "2026-12-30"
    assert any(doc.name == "Documento de información detallada de la consulta" for doc in item.documents)
