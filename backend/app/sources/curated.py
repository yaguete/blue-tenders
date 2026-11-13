"""Convocatorias revisadas a mano en config/curated/calls.yaml."""

from collections.abc import Iterable
from datetime import date, datetime

import yaml

from app.models.opportunity import (
    Analysis,
    AnalysisBlock,
    Citation,
    Deadline,
    DeadlineModel,
    Document,
    Fact,
    FactOrigin,
    NoticeKind,
    Opportunity,
    OpportunityKind,
    OpportunityType,
)
from app.settings import settings
from app.sources.base import Source
from app.vertical import Vertical


class CuratedSource(Source):
    id = "curated"
    kind = "api"

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del since, vertical
        path = settings.config_dir / "curated" / "calls.yaml"
        if not path.exists():
            return
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        yield from data

    def to_tender(self, raw: dict) -> Opportunity:
        external = str(raw["external_id"])
        facts = [
            Fact(
                field=item["field"],
                value=item.get("value"),
                origin=FactOrigin(item.get("origin", "manual")),
                confidence=float(item.get("confidence", 0.9)),
                quote=item.get("quote"),
            )
            for item in raw.get("facts") or []
        ]
        deadlines = [
            Deadline(
                phase=item["phase"],
                at=datetime.fromisoformat(item["at"]),
                timezone=item.get("timezone"),
            )
            for item in raw.get("deadlines") or []
        ]
        first = deadlines[0].at if deadlines else None
        summary = (raw.get("summary_en") or "").strip()
        quote = next((fact.quote for fact in facts if fact.quote), None)
        analysis = None
        if summary:
            analysis = Analysis(
                summary=summary,
                blocks=[
                    AnalysisBlock(
                        heading="Summary",
                        text=summary,
                        origin="extracted" if quote else "generated",
                        citations=[Citation(quote=quote, document_url=raw["url"])] if quote else [],
                    )
                ],
                model="manual",
            )
        kind = OpportunityKind(raw.get("kind", "grant"))
        url = raw["url"]
        documents = []
        if str(url).lower().split("?", 1)[0].endswith(".pdf"):
            documents.append(Document(url=url, name="Call (PDF)", kind="notice", access="fetch"))
        return Opportunity(
            id=Opportunity.make_id(self.id, external),
            source_id=self.id,
            external_id=external,
            url=url,
            documents=documents,
            type=OpportunityType.grant if kind == OpportunityKind.grant else OpportunityType.tender,
            kind=kind,
            notice=NoticeKind(raw.get("notice", "call_for_proposals")),
            title=raw["title"],
            title_en=raw["title"],
            summary_en=summary or None,
            language=raw.get("language"),
            programme_id=raw.get("programme_id"),
            funder_id=raw.get("funder_id"),
            deadline_model=DeadlineModel(raw.get("deadline_model", "single")),
            opens_at=datetime.fromisoformat(raw["opens_at"]) if raw.get("opens_at") else None,
            deadline_at=first,
            deadlines=deadlines,
            budget_total_eur=raw.get("budget_total_eur"),
            subsectors=list(raw.get("subsectors") or []),
            facts=facts,
            analysis=analysis,
            raw={},
        )
