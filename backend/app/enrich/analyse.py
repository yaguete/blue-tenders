"""Análisis de la ficha.

Sin clave de API se construye solo con texto que ya está en la oportunidad y se marca
como generated, salvo el resumen curado que trae cita. Con clave, Haiku reescribe
a partir de ese mismo texto y tiene que devolver citas; si falla, se queda el análisis local.
"""

import json
from datetime import UTC, datetime

from app.models.opportunity import Analysis, AnalysisBlock, Citation, Opportunity
from app.quality.text import plain_text
from app.quality.validate import quote_in_text


def analyse(opp: Opportunity) -> Opportunity:
    local = _from_fields(opp)
    remote = _from_llm(opp, local)
    opp.analysis = remote or local
    if opp.analysis and opp.analysis.summary and not opp.summary_en:
        opp.summary_en = opp.analysis.summary
    if opp.assessment is None and opp.analysis and opp.analysis.summary:
        from app.models.opportunity import Assessment

        opp.assessment = Assessment(summary=opp.analysis.summary)
    return opp


def _from_fields(opp: Opportunity) -> Analysis:
    source = opp.summary_en or opp.description or opp.title
    summary = plain_text(" ".join((source or "").split()))
    if len(summary) > 480:
        summary = summary[:477].rsplit(" ", 1)[0] + "…"
    blocks: list[AnalysisBlock] = []
    if summary:
        cited = _manual_quote(opp, "deadline_at")
        blocks.append(
            AnalysisBlock(
                heading="Summary",
                text=summary,
                origin="extracted" if cited else "generated",
                citations=[cited] if cited else [],
            )
        )
    bits = []
    if opp.eligible_entity_types:
        bits.append("Entity types: " + ", ".join(opp.eligible_entity_types) + ".")
    if opp.eligible_countries:
        bits.append("Geographies named on the record: " + ", ".join(opp.eligible_countries) + ".")
    if opp.consortium_required is True:
        extra = ""
        if opp.consortium_min_countries:
            extra = f" At least {opp.consortium_min_countries} countries."
        bits.append("A consortium is required." + extra)
    elif opp.consortium_required is False:
        bits.append("The programme rule does not require a consortium. Check the call.")
    if bits:
        blocks.append(
            AnalysisBlock(
                heading="Eligibility",
                text=" ".join(bits),
                origin="extracted",
                citations=[Citation(quote=f.quote, document_url=opp.url) for f in opp.facts if f.quote][:3],
            )
        )
    alerts = []
    if opp.consortium_min_countries and opp.consortium_min_countries >= 3:
        alerts.append(f"Requires a consortium of {opp.consortium_min_countries} countries.")
    if alerts:
        blocks.append(AnalysisBlock(heading="Alerts", text=" ".join(alerts), origin="generated"))
    return Analysis(summary=summary or None, blocks=blocks, model="fields", updated_at=datetime.now(UTC))


def _manual_quote(opp: Opportunity, field: str) -> Citation | None:
    for fact in opp.facts:
        if fact.field == field and fact.quote:
            return Citation(quote=fact.quote, document_url=opp.url)
    return None


def _loads_object(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise TypeError("el modelo no devolvió un objeto")
    return data


def _from_llm(opp: Opportunity, fallback: Analysis) -> Analysis | None:
    from app.settings import settings

    if not settings.anthropic_api_key or not (opp.description or opp.summary_en):
        return None
    corpus = (opp.summary_en or "") + "\n" + (opp.description or "")
    prompt = (
        "Summarise this funding call in English using only the text below. "
        "Return JSON {summary, blocks:[{heading, text, quote}]}. "
        "quote must be an exact excerpt. If you cannot quote it, omit the block. "
        "Do not say the reader is eligible.\n\n"
        + corpus[:12000]
    )
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.extract_model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if getattr(block, "text", None))
        data = _loads_object(text)
    except Exception as exc:  # noqa: BLE001  un fallo del modelo no debe tumbar la ficha
        print(f"[analyse] LLM skip: {exc}")
        return None
    blocks = []
    for raw in data.get("blocks") or []:
        quote = raw.get("quote") or ""
        if quote and not quote_in_text(quote, corpus):
            continue
        blocks.append(
            AnalysisBlock(
                heading=plain_text(str(raw.get("heading") or "Note")),
                text=plain_text(str(raw.get("text") or "")),
                origin="extracted" if quote else "generated",
                citations=[Citation(quote=quote, document_url=opp.url)] if quote else [],
            )
        )
    if not blocks:
        return None
    summary = plain_text(str(data.get("summary") or ""))
    return Analysis(
        summary=summary or fallback.summary,
        blocks=blocks,
        model=settings.extract_model,
        updated_at=datetime.now(UTC),
    )
