from datetime import UTC, datetime

from app.models.opportunity import NoticeKind, Opportunity, OpportunityKind, OpportunityType


def test_legacy_tender_type_derives_kind_and_notice():
    item = Opportunity(
        id="1", source_id="ted", external_id="1", url="https://example.test", title="Shore power"
    )
    assert item.type == OpportunityType.tender
    assert item.kind == OpportunityKind.tender
    assert item.notice == NoticeKind.contract_notice
    assert item.searchable()


def test_award_is_not_searchable():
    item = Opportunity(
        id="1",
        source_id="ted",
        external_id="1",
        url="https://example.test",
        title="Award",
        type=OpportunityType.award,
    )
    assert item.kind == OpportunityKind.tender
    assert item.notice == NoticeKind.award_notice
    assert not item.searchable()


def test_explicit_loan_is_kept():
    item = Opportunity(
        id="1",
        source_id="bdns",
        external_id="1",
        url="https://example.test",
        title="Loan",
        kind=OpportunityKind.loan,
        deadline_at=datetime(2026, 12, 1, tzinfo=UTC),
    )
    assert item.kind == OpportunityKind.loan
    assert item.type == OpportunityType.tender
