"""Listados oficiales leídos por configuración. Un YAML por sitio, no un adaptador.

Respeta robots.txt, se identifica y falla solo. Cero filas donde antes había
es un aviso: la página ha cambiado, no es que no haya convocatorias.
"""

import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
import yaml
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.jobs.notify import report_failure
from app.models.opportunity import (
    Budget,
    Buyer,
    Document,
    Fact,
    FactOrigin,
    Opportunity,
    OpportunityKind,
    OpportunityType,
)
from app.settings import settings
from app.sources.base import Source
from app.sources.dates import parse_when
from app.vertical import Vertical

USER_AGENT = "blue-tender/1.0 (official-call index)"
_ROBOTS: dict[str, RobotFileParser | None] = {}
_CURRENCY = {
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "nok": "NOK",
    "dkk": "DKK",
    "kr.": None,
}


def scraped_dir() -> Path:
    return settings.config_dir / "scraped"


def load_scraped_sources() -> list["ScrapedSource"]:
    folder = scraped_dir()
    if not folder.exists():
        return []
    return [ScrapedSource(path) for path in sorted(folder.glob("*.yaml"))]


def drop_message(previous: int | None, current: int) -> str | None:
    """Cero filas tras haber habido alguna: el selector ya no casa."""
    if current == 0 and previous:
        return (
            "el listado pasó de "
            f"{previous} filas a cero: ha cambiado la página, no es que no haya convocatorias"
        )
    return None


def rows_from_html(html: str, spec: dict, page_url: str, skipped: list[str] | None = None) -> list[dict]:
    tree = HTMLParser(html)
    nodes = tree.css(spec["row"])
    found = []
    for node in nodes:
        row = {name: _pick(node, selector) for name, selector in (spec.get("fields") or {}).items()}
        link = row.get("link")
        if link:
            row["link"] = urljoin(page_url, link)
        else:
            row["link"] = page_url
        if _skipped(row, spec.get("skip_if") or {}):
            if skipped is not None and row.get("link"):
                skipped.append(row["link"])
            continue
        if not _only(row, spec.get("only_if") or {}):
            continue
        if row.get("title") and row.get("link"):
            found.append(row)
    return _unique(found)


def rows_from_rss(xml: bytes, spec: dict) -> list[dict]:
    root = ET.fromstring(xml)
    found = []
    for item in root.iter():
        if _local(item.tag) != "item":
            continue
        row = {}
        for name, tag in (spec.get("fields") or {}).items():
            row[name] = _rss_text(item, str(tag))
        if row.get("title") and row.get("link"):
            found.append(row)
    return _unique(found)


def _unique(rows: list[dict]) -> list[dict]:
    found = []
    seen = set()
    for row in rows:
        if row["link"] in seen:
            continue
        seen.add(row["link"])
        found.append(row)
    return found


def parse_amount(text: str | None) -> tuple[float | None, str | None]:
    """Importe y moneda si los dos están escritos. `kr` a secas no es una moneda."""
    import re

    raw = " ".join(str(text or "").replace("\xa0", " ").split())
    if not raw:
        return None, None
    lowered = raw.lower()
    currency = None
    for token, code in _CURRENCY.items():
        if token in lowered or token in raw:
            currency = code
            break
    body = raw
    for token in _CURRENCY:
        body = re.sub(re.escape(token), " ", body, flags=re.IGNORECASE)
    body = re.sub(r"[^0-9.,]", "", body)
    return _to_float(body), currency


class ScrapedSource(Source):
    kind = "html"
    volume_alert = False

    def __init__(self, path: Path):
        self.path = path
        self.spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self.id = str(self.spec["id"])

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        del since, vertical
        self.closures = []
        page = self.spec["url"]
        if not _allowed(page):
            raise RuntimeError(f"{self.id}: robots.txt no permite {page}")
        self.closures = []
        skipped: list[str] = []
        with httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            rows = list(self._listing(client, page, skipped))
            message = drop_message(_previous_count(self.id), len(rows))
            _remember_count(self.id, len(rows))
            if message:
                report_failure(self.id, message)
                return
            self._close_known(skipped)
            self._absent_without_deadline([row.get("link") or "" for row in rows])
            detail = self.spec.get("detail") or {}
            for row in rows:
                if self._past_and_new(row):
                    continue
                if detail.get("fields") and row.get("link"):
                    time.sleep(1)
                    if not _allowed(row["link"]):
                        print(f"[{self.id}] robots.txt no permite {row['link']}")
                        continue
                    try:
                        response = client.get(row["link"])
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        print(f"[{self.id}] detalle {row['link']}: {exc}")
                    else:
                        extra = _detail_fields(response.text, detail["fields"])
                        for key, value in extra.items():
                            if value and not row.get(key):
                                row[key] = value
                                row[f"{key}_url"] = row["link"]
                row["page_url"] = page
                yield row

    def _listing(self, client: httpx.Client, page: str, skipped: list[str]) -> Iterable[dict]:
        if self.spec.get("list") == "rss":
            response = client.get(page)
            response.raise_for_status()
            yield from rows_from_rss(response.content, self.spec)
            return
        seen = 0
        url: str | None = page
        limit = int((self.spec.get("pagination") or {}).get("max") or 1)
        while url and seen < limit:
            response = client.get(url)
            response.raise_for_status()
            yield from rows_from_html(response.text, self.spec, url, skipped)
            seen += 1
            nxt = (self.spec.get("pagination") or {}).get("next")
            if not nxt:
                return
            tree = HTMLParser(response.text)
            link = tree.css_first(nxt)
            href = link.attributes.get("href") if link is not None else None
            url = urljoin(url, href) if href else None
            if url:
                time.sleep(1)

    def to_tender(self, raw: dict) -> Opportunity:
        title = str(raw.get("title") or "").strip()
        link = str(raw.get("link") or "").strip()
        if not title or not link:
            raise ValueError(f"{self.id}: fila sin título o sin enlace")
        language = str(self.spec.get("language") or "en")
        timezone = str(self.spec.get("timezone") or "UTC")
        formats = list(self.spec.get("dates") or [])
        deadline_text = raw.get("deadline_text")
        deadline = parse_when(deadline_text, language, formats, timezone)
        amount_text = raw.get("amount_text")
        amount, currency = parse_amount(amount_text)
        budget = None
        if amount is not None and currency:
            budget = Budget(
                amount=amount,
                currency=currency,
                amount_eur=amount if currency == "EUR" else None,
            )
        elif amount is not None:
            budget = Budget(amount=amount, currency=None)
        facts = []
        page = raw.get("deadline_text_url") or raw.get("page_url") or link
        if deadline_text:
            facts.append(
                Fact(
                    field="deadline_at",
                    value=deadline.isoformat() if deadline else None,
                    origin=FactOrigin.scraped,
                    confidence=0.85,
                    quote=str(deadline_text)[:500],
                    document_url=str(page),
                )
            )
        if amount_text:
            facts.append(
                Fact(
                    field="budget",
                    value=amount_text,
                    origin=FactOrigin.scraped,
                    confidence=0.85,
                    quote=str(amount_text)[:500],
                    document_url=str(raw.get("amount_text_url") or page),
                )
            )
        status = raw.get("status_text")
        if status:
            facts.append(
                Fact(
                    field="status_text",
                    value=str(status),
                    origin=FactOrigin.scraped,
                    confidence=0.85,
                    quote=str(status)[:200],
                    document_url=str(raw.get("page_url") or link),
                )
            )
        kind_name = str(self.spec.get("kind") or "tender")
        kind = OpportunityKind(kind_name)
        notice_type = OpportunityType.grant if kind == OpportunityKind.grant else OpportunityType.tender
        buyer = raw.get("buyer")
        country = self.spec.get("country") or None
        published = parse_when(raw.get("published_text"), language, formats, timezone)
        payload = {"link": link}
        if self.spec.get("prefilter") == "bypass":
            from app.sources.base import SOURCE_SUBSECTORS

            payload[SOURCE_SUBSECTORS] = [str(item) for item in self.spec.get("subsectors") or []]
        return Opportunity(
            id=Opportunity.make_id(self.id, link),
            source_id=self.id,
            external_id=link,
            url=link,
            type=notice_type,
            kind=kind,
            title=title,
            description=raw.get("description"),
            buyer=Buyer(name=str(buyer), country=country) if buyer else None,
            country=country,
            language=language,
            budget=budget,
            published_at=published.date() if published else None,
            deadline_at=deadline,
            documents=[Document(url=link, name="Official page", kind="html", access="fetch")],
            facts=facts,
            raw=payload,
        )

    def _past_and_new(self, row: dict) -> bool:
        """Una fila nueva con el plazo ya pasado no crea ficha. Una que ya existe se actualiza."""
        if not self.spec.get("skip_past"):
            return False
        language = str(self.spec.get("language") or "en")
        timezone = str(self.spec.get("timezone") or "UTC")
        deadline = parse_when(row.get("deadline_text"), language, list(self.spec.get("dates") or []), timezone)
        if deadline is None or deadline.date() >= date.today():
            return False
        try:
            from app.store import get_store

            return get_store().get(Opportunity.make_id(self.id, str(row.get("link")))) is None
        except Exception as exc:  # noqa: BLE001
            print(f"[{self.id}] {exc}")
            return False

    def _close_known(self, links: list[str]) -> None:
        try:
            from app.store import get_store

            store = get_store()
        except Exception as exc:  # noqa: BLE001
            print(f"[{self.id}] {exc}")
            return
        for link in links:
            item = store.get(Opportunity.make_id(self.id, link))
            if item is not None:
                self.closures.append(item.id)

    def _absent_without_deadline(self, links: list[str]) -> None:
        """Tres lecturas seguidas sin la fila, y sin plazo, cierran la ficha."""
        import json

        try:
            from app.store import get_store

            store = get_store()
        except Exception as exc:  # noqa: BLE001
            print(f"[{self.id}] {exc}")
            return
        previous = store.snapshot(f"{self.id}:seen") or {}
        try:
            state = json.loads(previous.get("body") or "{}")
        except json.JSONDecodeError:
            state = {}
        seen = {link for link in links if link}
        absent = dict(state.get("absent") or {})
        next_absent = {}
        for link, count in absent.items():
            if link in seen:
                continue
            count = int(count) + 1
            if count >= 3:
                item = store.get(Opportunity.make_id(self.id, link))
                if item is not None and item.deadline_at is None and item.closed_at is None:
                    self.closures.append(item.id)
                continue
            next_absent[link] = count
        for link in set(state.get("links") or []) - seen:
            if link not in next_absent and link not in absent:
                next_absent[link] = 1
        from datetime import UTC, datetime

        store.save_snapshot(
            f"{self.id}:seen",
            str(len(seen)),
            json.dumps({"links": sorted(seen), "absent": next_absent}),
            datetime.now(UTC).isoformat(),
        )


def _pick(node, selector: str | None) -> str | None:
    if not selector:
        return None
    if str(selector) in {".", ".@href"}:
        if selector == ".@href":
            return node.attributes.get("href")
        text = node.text(separator=" ", strip=True)
        return text or None
    if str(selector).startswith("contains:"):
        needle = str(selector).split(":", 1)[1].strip().lower()
        for element in node.css("strong, p, li, td, time"):
            text = " ".join(element.text(separator=" ", strip=True).split())
            if needle in text.lower() and len(text) < 240:
                return text
        return None
    if str(selector).startswith("label:"):
        return _by_label(node, str(selector).split(":", 1)[1])
    css, attr = (str(selector).rsplit("@", 1) + [None])[:2] if "@" in str(selector) else (selector, None)
    found = node.css_first(css) if css else node
    if found is None:
        return None
    if attr:
        return found.attributes.get(attr)
    text = found.text(separator=" ", strip=True)
    return text or None


def _by_label(node, label: str) -> str | None:
    want = " ".join(label.split()).lower()
    for element in node.css("h1, h2, h3, h4, dt, th, span, p"):
        if " ".join(element.text(separator=" ", strip=True).split()).lower() != want:
            continue
        current = element
        for _ in range(5):
            sibling = _next_element(current)
            if sibling is not None:
                timed = sibling.css_first("time") if sibling.tag != "-text" else None
                if timed is not None and timed.attributes.get("datetime"):
                    return timed.attributes.get("datetime")
                text = sibling.text(separator=" ", strip=True)
                if text and text.lower() != want:
                    return text
            if current.parent is None:
                break
            current = current.parent
    return None


def _next_element(node):
    sibling = node.next
    while sibling is not None and sibling.tag == "-text":
        sibling = sibling.next
    return sibling


def _detail_fields(html: str, fields: dict) -> dict:
    tree = HTMLParser(html)
    root = tree.body or tree.root
    if root is None:
        return {}
    return {name: _pick(root, selector) for name, selector in fields.items()}


def _only(row: dict, rules: dict) -> bool:
    if not rules:
        return True
    for field, words in rules.items():
        text = str(row.get(field) or "").lower()
        if not any(str(word).lower() in text for word in words):
            return False
    return True


def _skipped(row: dict, rules: dict) -> bool:
    for field, blocked in rules.items():
        text = str(row.get(field) or "").lower()
        if any(str(word).lower() in text for word in blocked):
            return True
    return False


def _rss_text(item: ET.Element, tag: str) -> str | None:
    for child in item:
        if _local(child.tag) == tag and child.text:
            return " ".join("".join(child.itertext()).split())
    return None


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _to_float(text: str) -> float | None:
    import re

    cleaned = text.strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", cleaned):
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _ROBOTS:
        parser = RobotFileParser()
        parser.set_url(origin + "/robots.txt")
        try:
            parser.read()
            _ROBOTS[origin] = parser
        except Exception as exc:  # noqa: BLE001  sin robots.txt se sigue, y se anota
            print(f"[scraped] robots.txt de {origin}: {exc}")
            _ROBOTS[origin] = None
    parser = _ROBOTS[origin]
    if parser is None:
        return True
    return parser.can_fetch(USER_AGENT, url)


def _previous_count(source_id: str) -> int | None:
    try:
        from app.store import get_store

        row = get_store().snapshot(f"{source_id}:rows")
    except Exception as exc:  # noqa: BLE001  sin almacén no hay con qué comparar
        print(f"[scraped] {source_id}: {exc}")
        return None
    if not row or not str(row.get("text_hash") or "").isdigit():
        return None
    return int(row["text_hash"])


def _remember_count(source_id: str, count: int) -> None:
    from datetime import UTC, datetime

    try:
        from app.store import get_store

        get_store().save_snapshot(f"{source_id}:rows", str(count), "", datetime.now(UTC).isoformat())
    except Exception as exc:  # noqa: BLE001
        print(f"[scraped] {source_id}: {exc}")
