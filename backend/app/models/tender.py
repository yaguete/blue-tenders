"""Alias de compatibilidad. El modelo nuevo es `app.models.opportunity`."""

from app.models.opportunity import (  # noqa: F401
    Analysis,
    AnalysisBlock,
    Assessment,
    Budget,
    Buyer,
    Citation,
    Deadline,
    DeadlineModel,
    Document,
    Fact,
    FactOrigin,
    NoticeKind,
    Opportunity,
    OpportunityKind,
    OpportunityStatus,
    OpportunityType,
)

Tender = Opportunity
