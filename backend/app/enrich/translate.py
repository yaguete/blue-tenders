"""Título y resumen al inglés. El original no se toca.

Si el idioma ya es inglés, title_en copia el título y no hay llamada.
Sin clave, title_en se queda como viniera de la fuente.
"""

from app.models.opportunity import Opportunity


def translate(opp: Opportunity) -> Opportunity:
    if opp.language == "en" and not opp.title_en:
        opp.title_en = opp.title
    if opp.language == "en" and opp.description and not opp.summary_en:
        text = " ".join(opp.description.split())
        opp.summary_en = text[:480]
    if opp.title_en or opp.language == "en":
        return opp
    _llm_title(opp)
    return opp


def _llm_title(opp: Opportunity) -> None:
    from app.settings import settings

    if not settings.anthropic_api_key:
        return
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.classify_model,
            max_tokens=1000,
            thinking={"type": "disabled"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Translate this funding title into English. "
                        "Return only the translation.\n\n" + opp.title
                    ),
                }
            ],
        )
        text = "".join(block.text for block in msg.content if getattr(block, "text", None)).strip()
        if text:
            opp.title_en = text
    except Exception as exc:  # noqa: BLE001  sin traducción se conserva el título original
        print(f"[translate] skip: {exc}")
