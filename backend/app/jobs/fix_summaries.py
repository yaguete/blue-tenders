"""Rehace resúmenes que hablan del texto en vez de la convocatoria.

No toca el hash ni el resto de la ficha. Con --dry-run solo cuenta.
"""

import argparse

from app.enrich.analyse import analyse
from app.enrich.translate import translate
from app.quality.text import is_meta, is_thin
from app.store import get_store


def needs_summary(item) -> bool:
    if is_meta(item.summary_en):
        return True
    if item.analysis and is_meta(item.analysis.summary):
        return True
    if item.analysis and any(is_meta(block.text) for block in item.analysis.blocks):
        return True
    return is_thin(item.description, item.title)


def run(store=None, *, dry_run: bool = False) -> int:
    store = store or get_store()
    chosen = [item for item in store.opportunities() if needs_summary(item)]
    if dry_run:
        print(f"[summaries] {len(chosen)} para rehacer")
        return len(chosen)
    for item in chosen:
        if is_meta(item.summary_en) or is_thin(item.description, item.title):
            item.summary_en = None
        translate(item)
        analyse(item)
        if is_meta(item.summary_en):
            item.summary_en = None
        if item.analysis and is_meta(item.analysis.summary):
            item.analysis.summary = None
            item.analysis.blocks = [block for block in item.analysis.blocks if not is_meta(block.text)]
        store.save_analysis(item)
    print(f"[summaries] {len(chosen)} rehechas")
    return len(chosen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
