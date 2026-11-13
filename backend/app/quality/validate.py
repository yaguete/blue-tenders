"""Validadores deterministas. No corrigen: devuelven errores."""

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
