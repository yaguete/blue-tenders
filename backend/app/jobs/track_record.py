"""Recalcula el historial guardado. No escribe en ingest_runs."""

import argparse

from app.partners.precompute import refresh_pending, refresh_source


def run(*, everything: bool = False, source: str | None = None, store=None) -> int:
    if source:
        return refresh_source(source, store)
    return refresh_pending(store, everything=everything)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--source", choices=("cordis", "ted_awards"), default=None)
    args = parser.parse_args()
    count = run(everything=args.all, source=args.source)
    print(f"[track-record] {count} convocatorias recalculadas")


if __name__ == "__main__":
    main()
