"""Páginas vigiladas. Un cambio de texto publica una ficha de información previa.

Se compara el texto visible, no los bytes. No hay plazo: la fecha es el día en que
se vio el cambio, y la cita es el texto nuevo.
"""

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime

import httpx
import yaml
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.enrich.watched_draft import change_quote
from app.models.opportunity import (
    Document,
    Fact,
    FactOrigin,
    Opportunity,
    OpportunityKind,
    OpportunityType,
)
from app.settings import settings
from app.sources.base import SOURCE_SUBSECTORS, Source
from app.vertical import Vertical

_SPACE = re.compile(r"\s+")
# El diff se hace contra el texto guardado. 20 000 se comía el final de una
# página de noticias y esas palabras parecían nuevas en el siguiente cambio.
_SNAPSHOT_BODY = 60_000


def visible_text(html: str, selector: str | None) -> str:
    """El selector puede casar con varias noticias. Se leen todas, no solo la primera."""
    tree = HTMLParser(html)
    if selector:
        nodes = tree.css(selector)
        raw = " ".join(node.text(separator=" ", strip=True) for node in nodes)
    else:
        node = tree.body
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
    # Un lunes sin cambios es lo normal, no una fuente caída.
    volume_alert = False

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
                store.save_snapshot(page["id"], digest, text[:_SNAPSHOT_BODY], datetime.now(UTC).isoformat())
                if not previous:
                    continue
                payload = {
                    "id": page["id"],
                    "url": page["url"],
                    "title": page.get("title") or page["url"],
                    "text": text,
                    "previous": previous.get("body") or "",
                    "detected_at": datetime.now(UTC).isoformat(),
                }
                if page.get("language"):
                    payload["language"] = str(page["language"])
                if page.get("country"):
                    payload["country"] = str(page["country"])
                kind = str(page.get("kind") or "")
                if kind in {item.value for item in OpportunityKind}:
                    payload["kind"] = kind
                subsectors = [str(item) for item in page.get("subsectors") or []]
                if subsectors:
                    payload[SOURCE_SUBSECTORS] = subsectors
                yield payload

    def to_tender(self, raw: dict) -> Opportunity:
        page_id = str(raw.get("id") or "").strip()
        url = str(raw.get("url") or "").strip()
        title = str(raw.get("title") or "").strip()
        detected = _detected(raw.get("detected_at"))
        if not page_id or not url or not title or detected is None:
            raise ValueError(f"página vigilada {page_id or url or '?'} sin url, título o fecha")
        quote = change_quote(str(raw.get("text") or ""), str(raw.get("previous") or ""))
        subsectors = raw.get(SOURCE_SUBSECTORS)
        kept = {SOURCE_SUBSECTORS: list(subsectors)} if isinstance(subsectors, list) and subsectors else {}
        kind = str(raw.get("kind") or "")
        return Opportunity(
            id=Opportunity.make_id(self.id, page_id),
            source_id=self.id,
            external_id=page_id,
            url=url,
            type=OpportunityType.prior_information_notice,
            kind=OpportunityKind(kind) if kind in {item.value for item in OpportunityKind} else None,
            title=title,
            description=quote or None,
            country=raw.get("country") or None,
            language=raw.get("language") or None,
            published_at=detected.date(),
            documents=[Document(url=url, name="Official page", kind="html", access="fetch")],
            facts=[
                Fact(
                    field="seen_at",
                    value=detected.date().isoformat(),
                    origin=FactOrigin.scraped,
                    confidence=0.7,
                    quote=quote[:500] or None,
                    document_url=url,
                )
            ],
            raw=kept,
        )


def _detected(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
