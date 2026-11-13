"""Markdown fuera: el LLM y algunos textos de fuente traen símbolos que la ficha no renderiza.

`plain_text` quita las marcas (encabezados, negritas, enlaces) y deja el contenido.
No traduce, no resume, no inventa: solo tacha sintaxis.
"""

import re
from html import unescape

_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+", re.MULTILINE)
_BULLET = re.compile(r"^ {0,3}[-*+][ \t]+", re.MULTILINE)
_QUOTE = re.compile(r"^ {0,3}>[ \t]?", re.MULTILINE)
_RULE = re.compile(r"^ {0,3}(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_CODE = re.compile(r"`{1,3}([^`]*)`{1,3}")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.DOTALL)
_ITALIC = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_STRAY = re.compile(r"\*\*|__|~~")
_WS = re.compile(r"[ \t]{2,}")


_META = re.compile(
    r"("
    r"\bthe (?:provided )?text\b"
    r"|\bthe notice (?:is|does|contains)\b"
    r"|\bthis summary\b"
    r"|\bis only a title\b"
    r"|\bno (?:further|other) details\b"
    r"|\bdoes not (?:specify|mention|include)\b"
    r")",
    re.IGNORECASE,
)
_CONTENT_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def is_meta(text: str | None) -> bool:
    """Un resumen que habla del texto en vez de la convocatoria."""
    if not text:
        return False
    return _META.search(text) is not None


def boilerplate_phrases() -> list[str]:
    from app.catalog import read_yaml_list
    from app.settings import settings

    path = settings.config_dir / "knowledge" / "boilerplate.yaml"
    phrases = []
    for row in read_yaml_list(path):
        if isinstance(row, str) and row.strip():
            phrases.append(row.strip())
        elif isinstance(row, dict) and str(row.get("text") or "").strip():
            phrases.append(str(row["text"]).strip())
    return phrases


def is_boilerplate(text: str | None) -> bool:
    folded = " ".join((text or "").casefold().split())
    if not folded:
        return False
    return any(phrase.casefold() in folded for phrase in boilerplate_phrases())


def content_words(text: str | None) -> int:
    return len(_CONTENT_WORD.findall(text or ""))


def adds_detail(text: str | None, title: str | None) -> bool:
    body = " ".join((text or "").split())
    name = " ".join((title or "").split())
    if not body or body.casefold() == name.casefold():
        return False
    return not is_boilerplate(body)


def is_thin(text: str | None, title: str | None) -> bool:
    """La fuente no da para un resumen: es el título, una frase de relleno, o muy corta."""
    body = " ".join((text or "").split())
    name = " ".join((title or "").split())
    if not body or body.casefold() == name.casefold():
        return True
    if is_boilerplate(body):
        return True
    return content_words(body) < 12


def plain_text(text: str | None) -> str:
    """`## Expected Outcome:` → `Expected Outcome:`; `**TRL 8**` → `TRL 8`."""
    if not text:
        return ""
    out = _LINK.sub(r"\1", unescape(text))
    out = _RULE.sub("", out)
    out = _HEADING.sub("", out)
    out = _BULLET.sub("", out)
    out = _QUOTE.sub("", out)
    out = _CODE.sub(r"\1", out)
    out = _BOLD.sub(r"\1", out)
    out = _ITALIC.sub(r"\1", out)
    out = _STRAY.sub("", out)
    out = _WS.sub(" ", out)
    return out.strip()