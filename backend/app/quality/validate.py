"""Validadores deterministas. No corrigen: devuelven errores."""

from datetime import date
from difflib import SequenceMatcher

from app.models.opportunity import Fact, FactOrigin, Opportunity

QUOTE_MIN_RATIO = 0.9


def validate_opportunity(opp: Opportunity) -> list[str]:
    errors: list[str] = []
    if opp.opens_at and opp.deadline_at and opp.opens_at > opp.deadline_at:
        errors.append("opens_at es posterior a deadline_at")
    for name in ("cofunding_min", "cofunding_max"):
        value = getattr(opp, name)
        if value is not None and not 0 <= value <= 100:
            errors.append(f"{name} fuera de 0–100")
    if (
        opp.cofunding_min is not None
        and opp.cofunding_max is not None
        and opp.cofunding_min > opp.cofunding_max
    ):
        errors.append("cofunding_min mayor que cofunding_max")
    for name in ("trl_min", "trl_max"):
        value = getattr(opp, name)
        if value is not None and not 1 <= value <= 9:
            errors.append(f"{name} fuera de 1–9")
    if opp.trl_min and opp.trl_max and opp.trl_min > opp.trl_max:
        errors.append("trl_min mayor que trl_max")
    if (
        opp.budget_total_eur is not None
        and opp.amount_max_eur is not None
        and opp.amount_max_eur > opp.budget_total_eur
    ):
        errors.append("el importe por proyecto supera el presupuesto total")
    return errors


def review_item(opp: Opportunity, reason: str, field: str | None, detail: str | None) -> dict:
    """Una fila de la cola. El id es estable para no duplicar el mismo aviso."""
    import hashlib

    digest = hashlib.sha1(f"{opp.id}:{reason}:{field or ''}".encode()).hexdigest()[:12]
    return {
        "id": digest,
        "opportunity_id": opp.id,
        "reason": reason,
        "field": field,
        "detail": (detail or "")[:500] or None,
        "resolved": False,
    }


def quote_in_text(quote: str, text: str) -> bool:
    """La cita tiene que estar en el documento. Se normaliza el espacio, no el sentido."""
    if not quote or not text:
        return False
    needle = " ".join(quote.split()).lower()
    haystack = " ".join(text.split()).lower()
    if needle in haystack:
        return True
    if len(needle) < 40:
        return False
    window = len(needle)
    step = max(20, window // 5)
    best = 0.0
    for i in range(0, max(1, len(haystack) - window + 1), step):
        best = max(best, SequenceMatcher(None, needle, haystack[i : i + window]).ratio())
        if best >= QUOTE_MIN_RATIO:
            return True
    return best >= QUOTE_MIN_RATIO


def apply_scraped_checks(opp: Opportunity, today: date | None = None) -> list[dict]:
    """Lo scrapeado se publica. Estos cuatro casos vacían el campo y van a la cola."""
    today = today or date.today()
    reviews = []
    for fact in list(opp.facts):
        if fact.origin != FactOrigin.scraped:
            continue
        if fact.field == "deadline_at" and (fact.value in (None, "") or not fact.quote):
            opp.deadline_at = None
            opp.deadlines = []
            reviews.append(review_item(opp, "unparseable_date", "deadline_at", fact.quote or str(fact.value or "")))
        if fact.field == "budget" and fact.value not in (None, "") and not _currency(opp):
            opp.budget = None
            opp.budget_total_eur = None
            reviews.append(review_item(opp, "amount_without_currency", "budget", fact.quote))
    if opp.deadline_at and opp.deadline_at.date() < today and _marked_open(opp):
        quote = next(
            (fact.quote for fact in opp.facts if fact.origin == FactOrigin.scraped and fact.field == "deadline_at"),
            None,
        )
        opp.deadline_at = None
        opp.deadlines = []
        reviews.append(review_item(opp, "past_deadline_open", "deadline_at", quote))
    for field, scraps in _scraped_by_field(opp).items():
        structured = [
            fact for fact in opp.facts if fact.field == field and fact.origin == FactOrigin.source and fact.value not in (None, "")
        ]
        if structured and scraps[0].value not in (None, "") and structured[0].value != scraps[0].value:
            reviews.append(review_item(opp, "scrape_conflict", field, scraps[0].quote))
    return reviews


def _currency(opp: Opportunity) -> bool:
    return bool(opp.budget and opp.budget.currency)


def _marked_open(opp: Opportunity) -> bool:
    for fact in opp.facts:
        if (
            fact.origin == FactOrigin.scraped
            and fact.field == "status_text"
            and str(fact.value or "").strip().lower() in {"open", "abierta", "ouvert", "aberto", "åben", "åpen"}
        ):
            return True
    return False


def _scraped_by_field(opp: Opportunity) -> dict[str, list[Fact]]:
    grouped: dict[str, list[Fact]] = {}
    for fact in opp.facts:
        if fact.origin == FactOrigin.scraped and fact.value not in (None, ""):
            grouped.setdefault(fact.field, []).append(fact)
    return grouped


def verify_fact(fact: Fact, document_text: str | None) -> Fact:
    """Un fact de LLM sin cita localizable no se publica como extracción."""
    if fact.origin != FactOrigin.llm:
        return fact
    if fact.quote and document_text and quote_in_text(fact.quote, document_text):
        return fact
    return fact.model_copy(update={"confidence": min(fact.confidence, 0.3), "quote": None})


CRITICAL_FIELDS = (
    "deadline_at",
    "eligible_entity_types",
    "consortium_required",
    "cofunding_min",
)


def extractions_agree(a: dict, b: dict, fields: tuple[str, ...] = CRITICAL_FIELDS) -> list[str]:
    """Campos críticos en los que dos extracciones no coinciden."""
    conflicts = []
    for field in fields:
        if a.get(field) != b.get(field):
            conflicts.append(field)
    return conflicts
