"""Páginas vigiladas. Se compara el texto, no los bytes, y un cambio no se publica."""

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime

import httpx
import yaml
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.models.opportunity import Opportunity
from app.settings import settings
from app.sources.base import Source
from app.vertical import Vertical

_SPACE = re.compile(r"\s+")


def visible_text(html: str, selector: str | None) -> str:
    tree = HTMLParser(html)
    node = tree.css_first(selector) if selector else tree.body
    raw = node.text(separator=" ", strip=True) if node is not None else tree.text(separator=" ")
    return _SPACE.sub(" ", raw or "").strip()


def changed(previous: str | None, current: str) -> bool:
    if not current:
        return False
    digest = hashlib.sha256(current.encode()).hexdigest()[:16]
    return previous != digest


class WatchedSource(Source):
    id = "watched"
    kind = "html"

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del since, vertical
        path = settings.config_dir / "watched.yaml"
        if not path.exists():
            return
        pages = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        from app.store import get_store

        store = get_store()
        with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "blue-tender/1.0"}) as client:
            for page in pages:
                try:
                    response = client.get(page["url"])
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    print(f"[watched] {page.get('url')}: {exc}")
                    continue
                text = visible_text(response.text, page.get("selector"))
                digest = hashlib.sha256(text.encode()).hexdigest()[:16]
                previous = store.snapshot(page["id"])
                if previous and previous.get("text_hash") == digest:
                    continue
                store.save_snapshot(page["id"], digest, text[:20000], datetime.now(UTC).isoformat())
                if previous:
                    yield {
                        "id": page["id"],
                        "url": page["url"],
                        "title": page.get("title") or page["url"],
                        "text": text,
                        "previous": previous.get("body") or "",
                    }

    def to_tender(self, raw: dict) -> Opportunity:
        raise ValueError(
            f"página vigilada {raw.get('id')} pendiente de revisión; no se indexa"
        )
