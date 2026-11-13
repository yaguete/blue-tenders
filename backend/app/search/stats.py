"""Cifras de la fila de encima de la búsqueda. No dependen de los filtros.

Los recuentos salen de una búsqueda sin filtros, así que las cajitas y el desplegable
de plazo no pueden dar números distintos. `curated` no cuenta: es un YAML del repo,
no una fuente que se comprueba.
"""

from datetime import date

from app.models.opportunity import Opportunity
from app.search.query import SearchFilters, search_opportunities

# Un límite alto, no infinito: sumar presupuestos no debe depender del tope de página.
ALL = 10**6


def platform_stats(items: list[Opportunity], freshness: dict, today: date | None = None) -> dict:
    counts = search_opportunities(items, SearchFilters(limit=0), today)["counts"]["deadline"]
    open_calls = search_opportunities(
        items, SearchFilters(deadline=["open", "closing_soon"], limit=ALL), today
    )["items"]
    budget = sum(item.budget_total_eur for item in open_calls if item.budget_total_eur)
    checked = [
        row
        for source, row in freshness.items()
        if source != "curated" and isinstance(row, dict) and row.get("status") == "ok"
    ]
    stamps = [row["finished_at"] for row in checked if row.get("finished_at")]
    return {
        "open": counts.get("open", 0),
        "closing_soon": counts.get("closing_soon", 0),
        "upcoming": counts.get("upcoming", 0),
        "closed": counts.get("closed", 0),
        "sources": len(checked),
        "checked_at": max(stamps) if stamps else None,
        "open_budget_eur": int(budget),
    }
