"""Carga el volcado de CORDIS. No es la ingesta de convocatorias y no toca sus marcas de agua."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.jobs.notify import report_failure
from app.partners.cordis import (
    SOURCES,
    content_hash,
    criteria_hash,
    fetch_zip,
    parse_file,
    parse_zip,
)
from app.store import get_store
from app.vertical import load_vertical


def run(
    source_id: str | None = None,
    *,
    file: Path | None = None,
    force: bool = False,
    store=None,
    vertical=None,
) -> int:
    store = store or get_store()
    vertical = vertical or load_vertical()
    criteria = criteria_hash(vertical)
    names = [source_id] if source_id else list(SOURCES)
    failed = 0
    for name in names:
        try:
            _one(name, store, vertical, criteria, file=file if source_id else None, force=force)
        except Exception as exc:  # noqa: BLE001  un volcado roto no tumba el otro
            report_failure(name, str(exc))
            failed += 1
    return 1 if failed else 0


def _one(source_id: str, store, vertical, criteria: str, *, file: Path | None, force: bool) -> None:
    spec = SOURCES[source_id]
    known = store.track_record_sources().get(source_id, {})
    if file is not None:
        parsed = parse_file(file, source_id=source_id, programme_id=spec["programme_id"], vertical=vertical)
        headers = {}
    else:
        etag = None if force or known.get("criteria_hash") != criteria else known.get("etag")
        modified = None if etag is None else known.get("last_modified")
        blob, headers = fetch_zip(spec["url"], etag=etag, modified=modified)
        if blob is None:
            print(f"[{source_id}] el volcado no ha cambiado")
            return
        parsed = parse_zip(
            blob, source_id=source_id, programme_id=spec["programme_id"], vertical=vertical
        )
    digest = content_hash(parsed)
    meta = {
        "etag": headers.get("etag") or known.get("etag"),
        "last_modified": headers.get("last-modified") or known.get("last_modified"),
        "criteria_hash": criteria,
        "content_hash": digest,
        "loaded_at": datetime.now(UTC).isoformat(),
        "projects": len(parsed["projects"]),
        "participations": len(parsed["participations"]),
    }
    same = known.get("content_hash") == digest and known.get("criteria_hash") == criteria
    if same and not force:
        store.save_track_record_source(source_id, **meta)
        print(f"[{source_id}] mismo corte, no se reescribe")
        return
    store.replace_cordis(
        source_id, parsed["orgs"], parsed["projects"], parsed["participations"], meta
    )
    from app.partners.precompute import refresh_source

    kind = "cordis" if source_id.startswith("cordis") else source_id
    refresh_source(kind, store, vertical)
    print(f"[{source_id}] {meta['projects']} proyectos, {meta['participations']} participaciones")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=sorted(SOURCES), default=None)
    parser.add_argument("--file", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.file and not args.source:
        parser.error("--file necesita --source")
    sys.exit(run(args.source, file=args.file, force=args.force))


if __name__ == "__main__":
    main()
