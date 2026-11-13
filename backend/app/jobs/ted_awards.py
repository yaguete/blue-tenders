"""Carga histórica de adjudicaciones de TED.

No entra en la ingesta diaria: consulta solo por texto completo (el CPV, sin ese filtro,
trae decenas de miles de avisos) y no escribe en `ingest_runs`, así que no mueve la marca
de agua de TED.
"""

import argparse
import sys
from datetime import UTC, date, datetime, timedelta

from app.pipeline import run as pipeline
from app.sources.ted import TedSource
from app.store import get_store
from app.vertical import load_vertical

AWARD_TYPES = ("can-standard", "can-social", "can-desg", "can-tran", "can-modif")


def run(days: int = 365, *, today: date | None = None, store=None) -> int:
    today = today or date.today()
    since = today - timedelta(days=days)
    vertical = load_vertical()
    source = TedSource(notice_types=AWARD_TYPES, include_cpv=False)
    notices = []
    for raw in source.fetch(since, vertical):
        try:
            notices.append(source.to_opportunity(raw))
        except Exception as exc:  # noqa: BLE001  un aviso roto no tumba la carga
            print(f"[ted-awards] skip: {exc}")
    notices = pipeline.dedupe(pipeline.prefilter(notices, vertical))
    kept = pipeline.enrich(notices, vertical)
    indexed = pipeline.index(kept)
    store = store or get_store()
    store.save_track_record_source(
        "ted-awards",
        since=since.isoformat(),
        loaded_at=datetime.now(UTC).isoformat(),
        projects=indexed,
        participations=indexed,
        content_hash=str(indexed),
    )
    from app.partners.precompute import refresh_source

    refresh_source("ted_awards", store)
    print(f"[ted-awards] {indexed} adjudicaciones desde {since}")
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    run(args.days)
    sys.exit(0)


if __name__ == "__main__":
    main()
