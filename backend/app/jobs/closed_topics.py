"""Carga única de topics cerrados. No entra en el cron.

Un cerrado con texto se queda en el índice y sale con el filtro de plazo «Closed».
Uno sin texto no se lista: la ficha no aportaría nada.
"""

from app.models.opportunity import Opportunity
from app.pipeline import run
from app.sources.eu_ft import EuFtSource
from app.vertical import load_vertical


def listed_when_closed(item: Opportunity) -> bool:
    return bool((item.description or "").strip())


def main() -> None:
    vertical = load_vertical()
    source = EuFtSource()
    # 31094503 es el estado «cerrado» del filtro público del portal.
    source.statuses = ("31094503",)
    rows = []
    for raw in source.fetch(__import__("datetime").date.min, vertical):
        try:
            item = source.to_tender(raw)
        except ValueError as exc:
            print(f"[closed] {exc}")
            continue
        item.listed = listed_when_closed(item)
        rows.append(item)
    rows = run.dedupe(run.prefilter(rows, vertical))
    kept = run.enrich(rows, vertical)
    listed = sum(1 for item in kept if item.listed)
    print(f"[closed] {run.index(kept)} topics, {listed} en la búsqueda")


if __name__ == "__main__":
    main()
