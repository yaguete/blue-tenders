"""Carga el fixture real de TED y las calls curadas en el almacén local.

No llama a la red ni al LLM. Sirve para arrancar la demo sin Supabase.
"""

import json
from datetime import date
from pathlib import Path

from app.pipeline.run import enrich, prefilter
from app.sources.curated import CuratedSource
from app.sources.ted import TedSource
from app.store import FileStore, get_store
from app.vertical import load_vertical

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ted" / "search_page.json"


def build() -> int:
    vertical = load_vertical("blue-economy")
    page = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ted = [TedSource().to_tender(notice) for notice in page["notices"]]
    curated_raw = list(CuratedSource().fetch(date(2020, 1, 1), vertical))
    curated = [CuratedSource().to_tender(row) for row in curated_raw]
    items = enrich(prefilter(ted, vertical), vertical)
    # Lo curado entra aunque el prefiltro no lo case: una persona lo revisó.
    already = {item.id for item in items}
    items.extend(enrich([row for row in curated if row.id not in already], vertical))
    store = get_store()
    if not isinstance(store, FileStore):
        return 0
    return store.upsert_opportunities(items)


if __name__ == "__main__":
    print(build())
