"""Descarga un documento de convocatoria una vez, al abrir el chat.

Guarda texto por página. Un fallo no se reintenta hasta pasadas 24 horas.
Los anexos generales de Horizon se cargan una vez, no en cada topic.
"""

import hashlib
import threading
from datetime import UTC, datetime, timedelta

import httpx

from app.catalog import read_yaml_list
from app.enrich.documents import _pages
from app.models.opportunity import Document, Opportunity
from app.settings import settings

SCAN_PAGE_CAP = 40
RETRY_AFTER = timedelta(hours=24)
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_BYTES: dict[str, bytes] = {}


def spawn(fn) -> None:
    """Los tests sustituyen esto para que la descarga ocurra antes de la respuesta."""
    threading.Thread(target=fn, daemon=True).start()


def file_id(opportunity_id: str, url: str) -> str:
    raw = f"{opportunity_id}|{url}".encode()
    return hashlib.sha1(raw).hexdigest()[:20]


def topic_pages_for(opp: Opportunity) -> list[dict]:
    """El texto guardado en la ficha, o el detalle del portal si la ficha solo tiene el título."""
    stored = (opp.description or "").strip()
    title = (opp.title or "").strip()
    summary = (opp.summary_en or "").strip()
    rich = stored if stored and stored != title and len(stored) > len(title) + 40 else ""
    if not rich and opp.source_id == "eu-ft":
        from app.sources.eu_ft import load_topic_text

        rich = load_topic_text(opp.topic_id or opp.external_id) or ""
    return section_pages(rich or stored or summary or title)


def _topic_is_thin(store, row: dict) -> bool:
    """Una ficha antigua dejó el título como si fuera el topic. Hay que volver a leerlo."""
    if row.get("kind") != "topic_text":
        return False
    text = "\n".join(page.get("text") or "" for page in store.pages_for(row["id"]))
    return "##" not in text and len(text) < 800


def section_pages(text: str) -> list[dict]:
    """El texto del topic usa `## Título` como página de cita."""
    body = (text or "").strip()
    if not body:
        return []
    if "\n## " not in f"\n{body}":
        return [{"page": 1, "heading": "Description", "text": body}]
    chunks = []
    for part in body.split("\n## "):
        part = part.strip()
        if not part:
            continue
        part = part.removeprefix("## ")
        heading, _, rest = part.partition("\n")
        chunks.append({"heading": heading.strip() or "Section", "text": (rest or heading).strip()})
    return [
        {"page": index, "heading": chunk["heading"], "text": chunk["text"]}
        for index, chunk in enumerate(chunks, start=1)
        if chunk["text"]
    ]


def shared_annexes() -> list[dict]:
    path = settings.config_dir / "knowledge" / "horizon-annexes.yaml"
    if not path.exists():
        return []
    return [row for row in read_yaml_list(path) if row.get("url")]


def annexes_for(opp: Opportunity) -> list[dict]:
    if opp.programme_id != "horizon-europe":
        return []
    return shared_annexes()


def prepare(store, opp: Opportunity, background: bool = True) -> list[dict]:
    """Deja cada documento en un estado y devuelve las filas. No bloquea si background."""
    rows = []
    docs = list(opp.documents)
    # Fichas ingeridas antes de guardar el texto del topic: se usa la descripción.
    has_text = bool(opp.description or opp.summary_en)
    if opp.source_id == "eu-ft" and has_text and not any(doc.kind == "topic_text" for doc in docs):
        docs = [
            Document(url=f"{opp.url}#topic-text", name="Topic text", kind="topic_text", access="inline")
        ] + [doc for doc in docs if doc.name != "Topic page"]
    for doc in docs:
        rows.append(_ensure(store, opp.id, doc, opp, background))
    for annex in annexes_for(opp):
        doc = Document(
            url=annex["url"],
            name=annex.get("name") or "General Annexes",
            kind="annex",
            access="fetch",
        )
        row = _ensure(store, "", doc, opp, background, version=str(annex.get("version") or ""))
        row["shared"] = True
        row["programme_id"] = annex.get("programme_id")
        rows.append(row)
    return rows


def _ensure(store, opportunity_id: str, doc: Document, opp: Opportunity, background: bool, version: str = "") -> dict:
    current = store.document_file_for(opportunity_id, doc.url)
    if current and current.get("version") == version and _fresh(current) and not _topic_is_thin(store, current):
        return current
    if doc.access == "link_only":
        return _save(store, opportunity_id, doc, "link_only", [], version=version)
    if doc.access == "inline":
        pages = topic_pages_for(opp) if doc.kind == "topic_text" else section_pages(
            opp.description or opp.summary_en or ""
        )
        status = "ok" if pages else "failed"
        return _save(
            store,
            opportunity_id,
            doc,
            status,
            pages,
            error=None if pages else "no text",
            version=version,
        )
    if current and current.get("status") == "fetching":
        return current
    placeholder = _save(store, opportunity_id, doc, "fetching", [], version=version)
    ident = placeholder["id"]

    def job() -> None:
        _download(store, ident, doc)

    if background:
        spawn(job)
    else:
        job()
    return store.document_file(ident) or placeholder


def _fresh(row: dict) -> bool:
    status = row.get("status")
    if status in {"ok", "link_only", "too_large", "scanned"}:
        return True
    if status != "failed":
        return False
    fetched = row.get("fetched_at")
    if not fetched:
        return False
    stamp = datetime.fromisoformat(fetched)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return datetime.now(UTC) - stamp < RETRY_AFTER


def _save(store, opportunity_id: str, doc: Document, status: str, pages: list[dict], error: str | None = None, version: str = "") -> dict:
    ident = file_id(opportunity_id, doc.url)
    row = {
        "id": ident,
        "opportunity_id": opportunity_id,
        "document_url": doc.url,
        "name": doc.name,
        "kind": doc.kind,
        "access": doc.access,
        "status": status,
        "pages": len(pages),
        "error": error,
        "fetched_at": datetime.now(UTC).isoformat(),
        "programme_id": None,
        "version": version,
    }
    store.save_document_file(row)
    if status in {"ok", "scanned"}:
        store.replace_pages(ident, pages)
    return row


def _download(store, ident: str, doc: Document) -> None:
    lock = _lock(ident)
    with lock:
        current = store.document_file(ident)
        if current and _fresh(current):
            return
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(doc.url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            _mark(store, ident, "failed", error=str(exc)[:300])
            return
        content = response.content
        content_type = response.headers.get("content-type", "")
        pages = [
            {"page": number, "heading": f"Page {number}", "text": text}
            for number, text in _pages(content, content_type, doc)
        ]
        if pages:
            _BYTES.pop(ident, None)
            _mark(store, ident, "ok", pages=pages)
            return
        count = _pdf_page_count(content, content_type, doc)
        if count is None:
            _mark(store, ident, "failed", error="no text")
            return
        if count > SCAN_PAGE_CAP:
            _mark(store, ident, "too_large", error=f"{count} pages")
            return
        _BYTES[ident] = content
        _mark(store, ident, "scanned", pages=[{"page": 1, "heading": "Scanned PDF", "text": ""}])


def cached_bytes(file_id_value: str) -> bytes | None:
    return _BYTES.get(file_id_value)


def _mark(store, ident: str, status: str, pages: list[dict] | None = None, error: str | None = None) -> None:
    current = store.document_file(ident) or {"id": ident}
    current["status"] = status
    current["error"] = error
    current["fetched_at"] = datetime.now(UTC).isoformat()
    current["pages"] = len(pages or [])
    store.save_document_file(current)
    if pages is not None and status == "ok":
        store.replace_pages(ident, pages)


def _pdf_page_count(content: bytes, content_type: str, doc: Document) -> int | None:
    if "pdf" not in content_type and not doc.url.lower().split("?", 1)[0].endswith(".pdf"):
        return None
    try:
        import pdfplumber
    except ImportError:
        return None
    import io

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return len(pdf.pages)
    except Exception:  # noqa: BLE001  un PDF ilegible no es texto
        return None


def _lock(ident: str) -> threading.Lock:
    with _LOCKS_GUARD:
        if ident not in _LOCKS:
            _LOCKS[ident] = threading.Lock()
        return _LOCKS[ident]


def load_ready(store, opp: Opportunity) -> tuple[list[dict], list[dict]]:
    """Documentos ya leídos y los que solo son un enlace."""
    readable = []
    links = []
    for row in store.document_files_for(opp.id) + store.document_files_for(""):
        if row.get("opportunity_id") == "" and opp.programme_id != "horizon-europe":
            continue
        if row.get("status") == "link_only":
            links.append(row)
            continue
        if row.get("status") not in {"ok", "scanned"}:
            continue
        pages = [page for page in store.pages_for(row["id"]) if page.get("text")]
        readable.append({**row, "pages": pages, "bytes": cached_bytes(row["id"])})
    return readable, links
