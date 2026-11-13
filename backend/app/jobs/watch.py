"""Revisa las páginas vigiladas y deja un borrador en la cola. No publica."""

from app.enrich.watched_draft import draft_change
from app.sources.watched import WatchedSource
from app.store import get_store
from app.vertical import load_vertical


def run() -> int:
    store = get_store()
    data = store.load()
    queued = 0
    for raw in WatchedSource().fetch(__import__("datetime").date.min, load_vertical()):
        draft = draft_change(raw)
        data["reviews"].append(draft)
        queued += 1
    if queued:
        store.save(data)
    print(f"[watched] {queued} cambios en revisión")
    return queued


if __name__ == "__main__":
    run()
