"""Carga única de topics cerrados. No entra en el cron ni en la búsqueda de abiertas."""

from app.pipeline import run
from app.sources.eu_ft import EuFtSource
from app.vertical import load_vertical


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
        item.listed = False
        rows.append(item)
    kept = run.enrich(rows, vertical)
    print(f"[closed] {run.index(kept)} topics fuera de la búsqueda")


if __name__ == "__main__":
    main()
