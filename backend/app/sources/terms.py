"""Términos de búsqueda de un vertical, leídos del YAML. Nada de listas en Python."""

from app.vertical import Vertical


def search_pairs(vertical: Vertical, source_id: str) -> list[tuple[str, str]]:
    """`(subsector, término)` en el orden del YAML, sin repetir el mismo par."""
    grouped = (vertical.search_terms or {}).get(source_id) or {}
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for subsector, terms in grouped.items():
        for term in terms or []:
            text = str(term).strip()
            key = (subsector, text.casefold())
            if not text or key in seen:
                continue
            seen.add(key)
            pairs.append((subsector, text))
    return pairs
