"""Opportunity canónico. Ver docs/opportunity-schema.md.

`Tender` en `app.models.tender` es un alias de esta clase. El campo `type` se conserva
porque el adaptador de TED y sus tests lo usan; `kind` y `notice` se rellenan a partir de él.
"""

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class OpportunityType(str, Enum):
    tender = "tender"
    grant = "grant"
    prior_information_notice = "prior_information_notice"
    award = "award"


class OpportunityKind(str, Enum):
    grant = "grant"
    tender = "tender"
    loan = "loan"
    equity = "equity"
    prize = "prize"
    technical_assistance = "technical_assistance"
    blended = "blended"


class NoticeKind(str, Enum):
    contract_notice = "contract_notice"
    pin = "pin"
    award_notice = "award_notice"
    call_for_proposals = "call_for_proposals"
    cascade = "cascade"
    continuous = "continuous"


class DeadlineModel(str, Enum):
    single = "single"
    two_stage = "two_stage"
    multiple_cutoff = "multiple_cutoff"
    continuous = "continuous"


class OpportunityStatus(str, Enum):
    open = "open"
    forthcoming = "forthcoming"
    closed = "closed"


class FactOrigin(str, Enum):
    source = "source"
    programme_rule = "programme_rule"
    llm = "llm"
    manual = "manual"
    scraped = "scraped"


_KIND_FROM_TYPE = {
    OpportunityType.tender: (OpportunityKind.tender, NoticeKind.contract_notice),
    OpportunityType.grant: (OpportunityKind.grant, NoticeKind.call_for_proposals),
    OpportunityType.prior_information_notice: (OpportunityKind.tender, NoticeKind.pin),
    OpportunityType.award: (OpportunityKind.tender, NoticeKind.award_notice),
}


class Buyer(BaseModel):
    name: str
    country: str | None = None
    kind: str | None = None


class Budget(BaseModel):
    amount: float | None = None
    currency: str | None = None
    amount_eur: float | None = None


class Document(BaseModel):
    url: str
    name: str | None = None
    kind: str | None = None
    # fetch: se descarga al abrir el chat. inline: el texto ya está en la ficha.
    # link_only: se enseña el enlace y no se lee (pliegos fuera de TED).
    access: str = "fetch"


class Assessment(BaseModel):
    """Forma antigua del análisis. La ficha nueva usa `Analysis`."""

    summary: str | None = None
    evaluation_criteria: list[str] = []
    timeline: list[str] = []
    requirements: list[str] = []


class Citation(BaseModel):
    document_url: str | None = None
    page: int | None = None
    quote: str | None = None


class AnalysisBlock(BaseModel):
    heading: str
    text: str
    origin: Literal["extracted", "generated"] = "generated"
    citations: list[Citation] = []


class Analysis(BaseModel):
    summary: str | None = None
    blocks: list[AnalysisBlock] = []
    model: str | None = None
    updated_at: datetime | None = None


class Fact(BaseModel):
    field: str
    value: Any = None
    origin: FactOrigin
    confidence: float = Field(ge=0, le=1)
    document_url: str | None = None
    page: int | None = None
    quote: str | None = None
    model: str | None = None


class Deadline(BaseModel):
    phase: str
    at: datetime
    timezone: str | None = None


class Opportunity(BaseModel):
    id: str
    source_id: str
    external_id: str
    url: str
    type: OpportunityType = OpportunityType.tender
    kind: OpportunityKind | None = None
    notice: NoticeKind | None = None
    instruments: list[str] = []
    title: str
    title_en: str | None = None
    summary_en: str | None = None
    description: str | None = None
    buyer: Buyer | None = None
    funder_id: str | None = None
    programme_id: str | None = None
    call_id: str | None = None
    topic_id: str | None = None
    type_of_action: str | None = None
    mission_ocean: bool = False
    country: str | None = None
    region: str | None = None
    cpv: list[str] = []
    nuts: list[str] = []
    budget: Budget | None = None
    budget_total_eur: float | None = None
    amount_min_eur: float | None = None
    amount_max_eur: float | None = None
    cofunding_min: float | None = None
    cofunding_max: float | None = None
    published_at: date | None = None
    opens_at: datetime | None = None
    deadline_at: datetime | None = None
    deadline_model: DeadlineModel = DeadlineModel.single
    deadlines: list[Deadline] = []
    status: OpportunityStatus | None = None
    language: str | None = None
    documents: list[Document] = []
    vertical: str | None = None
    subsectors: list[str] = []
    relevance: float | None = None
    sea_basins: list[str] = []
    trl_min: int | None = None
    trl_max: int | None = None
    sdgs: list[int] = []
    eligible_entity_types: list[str] = []
    eligible_countries: list[str] = []
    consortium_required: bool | None = None
    consortium_min_partners: int | None = None
    consortium_min_countries: int | None = None
    assessment: Assessment | None = None
    analysis: Analysis | None = None
    facts: list[Fact] = []
    content_hash: str | None = None
    review_status: str | None = None
    listed: bool = True
    # Identificador que otra fuente también puede traer (expediente, ocid). Vacío si no hay.
    dedupe_key: str | None = None
    # Cierre explícito: cancelación de la fuente, o una página que ya no lista la convocatoria.
    closed_at: datetime | None = None
    raw: dict = Field(default_factory=dict, exclude=True)
    # No se guarda. La ingesta lo vuelca en la cola de revisión al indexar.
    review_items: list[dict] = Field(default_factory=list, exclude=True)

    @field_validator("raw", mode="before")
    @classmethod
    def empty_raw(cls, value: Any) -> dict:
        # Al guardar en Supabase el campo no se escribe, así que vuelve como null.
        return value if isinstance(value, dict) else {}

    @model_validator(mode="after")
    def fill_derived(self) -> "Opportunity":
        derived_kind, derived_notice = _KIND_FROM_TYPE[self.type]
        if self.kind is None:
            self.kind = derived_kind
        if self.notice is None:
            self.notice = derived_notice
        if not self.instruments:
            self.instruments = [self.kind.value]
        if self.budget and self.budget.amount_eur is not None and self.budget_total_eur is None:
            if self.kind == OpportunityKind.tender:
                self.budget_total_eur = self.budget.amount_eur
            elif self.amount_max_eur is None:
                self.amount_max_eur = self.budget.amount_eur
        if self.content_hash is None:
            self.content_hash = self.compute_hash()
        if self.status is None:
            self.status = compute_status(self)
        return self

    def compute_hash(self) -> str:
        winners = ""
        award = ""
        call_title = ""
        for fact in self.facts:
            if fact.field == "winners":
                winners = json.dumps(fact.value, ensure_ascii=False, sort_keys=True)
            elif fact.field == "award_value_eur":
                award = str(fact.value)
            elif fact.field == "call_title":
                call_title = str(fact.value)
        parts = [
            self.title,
            self.description or "",
            self.deadline_at.isoformat() if self.deadline_at else "",
            self.opens_at.isoformat() if self.opens_at else "",
            str(self.budget.amount if self.budget else ""),
            str(self.budget.currency if self.budget else ""),
            str(self.budget_total_eur or ""),
            str(self.amount_min_eur or ""),
            str(self.amount_max_eur or ""),
        ]
        # Solo si la fuente los trae: si no, el hash de lo ya guardado no cambia.
        if winners:
            parts.append(winners)
        if award:
            parts.append(award)
        if call_title:
            parts.append(call_title)
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]

    @staticmethod
    def make_id(source_id: str, external_id: str) -> str:
        return hashlib.sha1(f"{source_id}:{external_id}".encode()).hexdigest()[:16]

    def searchable(self) -> bool:
        return self.listed and self.notice != NoticeKind.award_notice


def compute_status(opp: Opportunity, today: date | None = None) -> OpportunityStatus:
    today = today or date.today()
    if opp.closed_at and opp.closed_at.date() <= today:
        return OpportunityStatus.closed
    if opp.notice == NoticeKind.award_notice:
        return OpportunityStatus.closed
    if opp.deadline_model == DeadlineModel.continuous and opp.deadline_at is None:
        opened = opp.opens_at.date() if opp.opens_at else None
        if opened and opened > today:
            return OpportunityStatus.forthcoming
        return OpportunityStatus.open
    if opp.opens_at and opp.opens_at.date() > today and (
        opp.deadline_at is None or opp.deadline_at.date() >= today
    ):
        return OpportunityStatus.forthcoming
    if opp.deadline_at and opp.deadline_at.date() < today:
        return OpportunityStatus.closed
    if opp.deadline_at or opp.opens_at:
        return OpportunityStatus.open
    # Sin plazo ni apertura: visible un tiempo si se acaba de publicar (BOE, HTML sin fecha leíble).
    # Pasados 90 días, o si no hay ni fecha de publicación, se queda cerrada.
    published = opp.published_at
    if published is not None and (today - published).days <= 90:
        return OpportunityStatus.open
    return OpportunityStatus.closed
