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


def test_a_call_without_a_date_stays_closed_unless_it_was_just_published():
    from datetime import date, timedelta

    from app.models.opportunity import OpportunityStatus, compute_status

    bare = Opportunity(
        id="1", source_id="boe", external_id="1", url="https://example.test", title="Bases"
    )
    assert compute_status(bare, date(2026, 11, 13)) == OpportunityStatus.closed
    recent = bare.model_copy(update={"published_at": date(2026, 11, 1)})
    assert compute_status(recent, date(2026, 11, 13)) == OpportunityStatus.open
    old = bare.model_copy(update={"published_at": date(2026, 11, 13) - timedelta(days=91)})
    assert compute_status(old, date(2026, 11, 13)) == OpportunityStatus.closed
    closed = bare.model_copy(
        update={"published_at": date(2026, 11, 1), "closed_at": datetime(2026, 11, 10, tzinfo=UTC)}
    )
    assert compute_status(closed, date(2026, 11, 13)) == OpportunityStatus.closed
