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