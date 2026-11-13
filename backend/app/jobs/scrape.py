"""Recorre los YAML de config/scraped. Cada sitio es una ejecución y falla solo."""

import sys

from app.jobs.ingest_daily import run_one
from app.sources.scraped import load_scraped_sources


def main() -> None:
    code = 0
    sources = load_scraped_sources()
    if not sources:
        print("[scrape] no hay sitios en config/scraped")
        sys.exit(0)
    for source in sources:
        try:
            code = max(code, run_one(source.id))
        except Exception as exc:  # noqa: BLE001  un sitio no tumba el resto
            print(f"[{source.id}] {exc}")
            code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
