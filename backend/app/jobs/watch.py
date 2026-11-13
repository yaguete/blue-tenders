"""Revisa las páginas vigiladas y publica la ficha cuando el texto cambia.

Sin plazo inventado. Lo que no nombra el sector no pasa el prefiltro, salvo que
la página declare sus subsectores en el YAML.
"""

from datetime import date

from app.pipeline import run as pipeline
from app.store import get_store
from app.vertical import load_vertical


def run() -> int:
    vertical = load_vertical()
    store = get_store()
    tenders = pipeline.ingest("watched", date.min, vertical)
    filtered = pipeline.prefilter(tenders, vertical)
    kept, _skipped = pipeline.split_eu(filtered)
    tenders = pipeline.dedupe(kept, store)
    tenders = pipeline.enrich(tenders, vertical)
    indexed = pipeline.index(tenders)
    print(f"[watched] {indexed} fichas")
    return indexed


if __name__ == "__main__":
    run()
