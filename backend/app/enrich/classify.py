"""Clasificación por subsector. Reglas siempre; Haiku solo si hay clave y el texto es ambiguo."""

import json

from app.catalog import sdgs_for
from app.models.opportunity import Fact, FactOrigin, Opportunity
from app.vertical import Vertical


def classify_rules(opp: Opportunity, vertical: Vertical) -> Opportunity:
    from app.pipeline.run import _keyword_words, _mentions, _tokens
    from app.sources.base import source_subsectors

    tokens = _tokens(f"{opp.title} | {opp.title_en or ''} | {opp.summary_en or ''} | {opp.description or ''}")
    # Aquí solo se ven el título y la descripción. Lo que la fuente encontró buscando en el
    # texto completo del registro también cuenta: sin esto, un anuncio que nombra el sector
    # en el cuerpo y no en el título se quedaría sin subsector y se descartaría.
    at_source = set(source_subsectors(opp.raw))
    matched = []
    in_title = False
    for sub in vertical.active_subsectors:
        words = [_keyword_words(k) for k in sub.keywords]
        local = any(_mentions(tokens, w) for w in words)
        in_title = in_title or local
        if local or sub.id in at_source:
            matched.append(sub.id)
    opp.subsectors = matched
    opp.vertical = vertical.id
    opp.relevance = {1: 0.72, 0: None}.get(len(matched), 0.5)
    if len(matched) > 1:
        opp.relevance = 0.5
    # Una mención en algún punto del cuerpo es una prueba más débil que el título: puede ser
    # una referencia de pasada. Se clasifica, pero con menos confianza y dejando constancia.
    only_at_source = bool(matched) and not in_title
    if only_at_source:
        opp.relevance = 0.4
    if matched:
        opp.sdgs = sdgs_for(vertical.id, matched)
        opp.facts.append(
            Fact(
                field="subsectors",
                value=matched,
                origin=FactOrigin.programme_rule,
                confidence=opp.relevance or 0.5,
                model="source-fulltext" if only_at_source else "keyword-rules",
            )
        )
    return opp


def classify(opp: Opportunity, vertical: Vertical) -> Opportunity:
    """Las reglas marcan candidatos. El LLM solo desempata si hay clave y más de un subsector."""
    classify_rules(opp, vertical)
    if len(opp.subsectors) <= 1:
        return opp
    choice = _llm_pick(opp, vertical)
    if choice and choice in opp.subsectors:
        opp.subsectors = [choice]
        opp.relevance = 0.8
        opp.facts.append(
            Fact(
                field="subsectors",
                value=[choice],
                origin=FactOrigin.llm,
                confidence=0.8,
                model="haiku",
            )
        )
    return opp


def _llm_pick(opp: Opportunity, vertical: Vertical) -> str | None:
    from app.settings import settings

    if not settings.anthropic_api_key:
        return None
    options = [s for s in vertical.active_subsectors if s.id in opp.subsectors]
    prompt = {
        "title": opp.title_en or opp.title,
        "text": (opp.description or "")[:4000],
        "options": [{"id": s.id, "name": s.name} for s in options],
        "instruction": "Pick one id or null if none really fit. Reply JSON {\"id\": string|null}.",
    }
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.classify_model,
            max_tokens=200,
            messages=[{"role": "user", "content": json.dumps(prompt)}],
        )
        text = "".join(block.text for block in msg.content if getattr(block, "text", None))
        return json.loads(text).get("id")
    except Exception as exc:  # noqa: BLE001  si Haiku falla se quedan las reglas
        print(f"[classify] LLM skip: {exc}")
        return None
