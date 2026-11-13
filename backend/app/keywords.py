"""Vocabulario de un vertical: cómo se leen y se comparan sus keywords.

Lo usan el prefiltro y el clasificador (comparación local sobre título y descripción) y los
adaptadores que saben buscar por texto completo en su fuente (TED).
"""

import re
import unicodedata

_WORD = re.compile(r"[^\W_]+")
_KEYWORD_WORD = re.compile(r"[^\W_]+\*?")
# Cuántas palabras de más puede haber entre las de una keyword:
# "offshore and onshore wind" tiene que casar con "offshore wind".
SLACK = 4
# Un prefijo más corto casaría con medio diccionario ("ops*" con "opsional", "opstelling"…).
MIN_PREFIX = 4


def plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    """Palabras en minúsculas y sin acentos ("Eólica" y "eolica" son la misma)."""
    return _WORD.findall(plain(text))


def keyword_words(keyword: str) -> list[str]:
    """Palabras de una keyword. Una palabra acabada en `*` casa por prefijo.

    El prefijo existe para los compuestos del alemán: `landstrom*` casa con
    "Landstromanlage" y "Landstromversorgung", que como palabra completa no casarían.
    """
    words = _KEYWORD_WORD.findall(plain(keyword))
    for w in words:
        if w.endswith("*") and len(w) - 1 < MIN_PREFIX:
            raise ValueError(
                f"keyword {keyword!r}: el prefijo {w!r} es demasiado corto "
                f"(mínimo {MIN_PREFIX} letras)"
            )
    return words


def same_word(token: str, word: str) -> bool:
    """Palabra completa, con su plural. "ops" no casa con "workshops"."""
    if word.endswith("*"):
        return token.startswith(word[:-1])
    return token == word or token == word + "s" or token == word + "es"


def _fast_has(token_set: set[str], keyword: list[str]) -> bool:
    """Condición necesaria y barata: cada palabra de la keyword está en el conjunto.

    `mentions` sigue decidiendo (cercanía y orden libre). Sin este corte, recorrer un
    volcado de decenas de miles de proyectos tarda minutos.
    """
    for word in keyword:
        if word.endswith("*"):
            prefix = word[:-1]
            if not any(token.startswith(prefix) for token in token_set):
                return False
        elif word not in token_set and f"{word}s" not in token_set and f"{word}es" not in token_set:
            return False
    return True


def matched_subsectors(text: str, subsectors, *, include_project_keywords: bool = False) -> list[str]:
    """Subsectores cuyo vocabulario nombra el texto, con las mismas reglas que el prefiltro.

    `project_keywords` solo entra cuando se pide: es el vocabulario del historial, no el de
    las convocatorias abiertas.
    """
    text_tokens = tokens(text)
    token_set = set(text_tokens)
    found = []
    for subsector in subsectors:
        words = list(subsector.keywords)
        if include_project_keywords:
            words = words + list(subsector.project_keywords)
        compiled = [keyword_words(keyword) for keyword in words]
        if any(_fast_has(token_set, keyword) and mentions(text_tokens, keyword) for keyword in compiled):
            found.append(subsector.id)
    return found


def mentions(text_tokens: list[str], keyword: list[str]) -> bool:
    """Todas las palabras de la keyword aparecen cerca unas de otras, en cualquier orden."""
    if not keyword:
        return False
    span = len(keyword) + SLACK
    for i, tok in enumerate(text_tokens):
        if not any(same_word(tok, w) for w in keyword):
            continue
        window = text_tokens[i : i + span]
        if all(any(same_word(t, w) for t in window) for w in keyword):
            return True
    return False
