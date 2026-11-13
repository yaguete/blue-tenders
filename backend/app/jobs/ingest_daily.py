"""Una fuente por ejecución. La marca de agua cubre el hueco si el día anterior falló.

`watched` no entra: esas páginas tienen su propio trabajo y no se publican solas.
"""

import argparse
import sys
from datetime import UTC, date, datetime, timedelta

from app.jobs.notify import beat, report_failure
from app.pipeline import run
from app.store import get_store
from app.vertical import load_vertical

OVERLAP_DAYS = 2
DEFAULT_LOOKBACK = 1


def since_for(source: str, today: date, days: int | None, store=None) -> date:
    if days is not None:
        return today - timedelta(days=days)
    store = store or get_store()
    previous = store.last_success_until(source)
    if not previous:
        return today - timedelta(days=DEFAULT_LOOKBACK)
    if isinstance(previous, str):
        previous = date.fromisoformat(previous)
    return previous - timedelta(days=OVERLAP_DAYS)


def _default_execute(source: str, since: date, vertical):
    tenders = run.ingest(source, since, vertical)
    raw_count = len(tenders)
    if source == "curated":
        tenders = run.dedupe(tenders)
    else:
        tenders = run.dedupe(run.prefilter(tenders, vertical))
    kept = len(tenders)
    tenders = run.enrich(tenders, vertical)
    indexed = run.index(tenders)
    return {"raw_count": raw_count, "kept": kept, "indexed": indexed, "unchanged": raw_count - kept}


def run_one(source: str, days: int | None = None, *, today: date | None = None, execute=None, store=None) -> int:
    if source == "watched":
        print("[watched] no se ingiere desde aquí")
        return 0
    today = today or date.today()
    store = store or get_store()
    now = datetime.now(UTC)
    run_id = store.begin_ingest(source, now)
    if run_id is None:
        print(f"[{source}] ya hay una ejecución en curso")
        return 0
    start = since_for(source, today, days, store)
    previous_raw = store.last_ok_raw(source)
    try:
        stats = (execute or _default_execute)(source, start, load_vertical(None))
    except Exception as exc:  # noqa: BLE001  el registro tiene que quedar aunque la fuente rompa
        store.finish_ingest(
            run_id,
            finished_at=datetime.now(UTC).isoformat(),
            status="failed",
            since=start.isoformat(),
            until=today.isoformat(),
            message=str(exc)[:500],
        )
        report_failure(source, str(exc))
        return 1
    store.finish_ingest(
        run_id,
        finished_at=datetime.now(UTC).isoformat(),
        status="ok",
        since=start.isoformat(),
        until=today.isoformat(),
        **stats,
        message=None,
    )
    raw = int(stats.get("raw_count") or 0)
    if raw == 0 or (previous_raw and raw < previous_raw * 0.5):
        report_failure(source, f"volume {raw}, previous {previous_raw}")
    beat()
    print(f"[{source}] {stats.get('indexed', 0)} indexados desde {start}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--days", type=int, default=None)
    args = parser.parse_args()
    sys.exit(run_one(args.source, args.days))


if __name__ == "__main__":
    main()
