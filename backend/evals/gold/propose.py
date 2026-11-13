"""Escribe candidatos. No confirma nada."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from app.pipeline.run import prefilter
from app.sources.ted import TedSource
from app.vertical import load_vertical

OUT = Path(__file__).with_name("candidates.jsonl")
FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ted" / "search_page.json"


def from_notices(notices: list[dict], vertical) -> list[dict]:
    src = TedSource()
    rows = []
    parsed = []
    for raw in notices:
        try:
            parsed.append(src.to_tender(raw))
        except ValueError:
            continue
    kept = {item.id for item in prefilter(parsed, vertical)}
    for item in parsed:
        rows.append(
            {
                "source_id": item.source_id,
                "external_id": item.external_id,
                "title": item.title_en or item.title,
                "proposed_relevant": item.id in kept,
                "proposed_subsectors": [],
                "status": "proposed",
                "reviewer": None,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=150)
    args = parser.parse_args()
    vertical = load_vertical("blue-economy")
    import os

    if os.environ.get("TED_LIVE"):
        notices = []
        for raw in TedSource().fetch(date.today() - timedelta(days=7), vertical):
            notices.append(raw)
            if len(notices) >= args.limit:
                break
    else:
        notices = json.loads(FIXTURE.read_text(encoding="utf-8"))["notices"]
    rows = from_notices(notices, vertical)[: args.limit]
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"{len(rows)} candidatos en {OUT.name}. status=proposed, sin confirmar.")


if __name__ == "__main__":
    main()
