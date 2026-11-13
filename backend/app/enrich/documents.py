"""Descarga y troceo de documentos. Apagado salvo ENRICH_DOCUMENTS=1.

No guarda el PDF en el repositorio: solo texto por páginas, y solo si la descarga funciona.
"""

import io
import re

import httpx

from app.models.opportunity import Document, Opportunity


def fetch_documents(opp: Opportunity) -> list[dict]:
    from app.settings import settings

    if not settings.enrich_documents:
        return []
    chunks = []
    for doc in opp.documents:
        if not doc.url:
            continue
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(doc.url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"[documents] {doc.url}: {exc}")
            continue
        pages = _pages(response.content, response.headers.get("content-type", ""), doc)
        for number, text in pages:
            for piece in _chunks(text):
                chunks.append(
                    {
                        "opportunity_id": opp.id,
                        "document_url": doc.url,
                        "page": number,
                        "text": piece,
                    }
                )
    return chunks


def _pages(content: bytes, content_type: str, doc: Document) -> list[tuple[int, str]]:
    if "pdf" in content_type or doc.url.lower().endswith(".pdf"):
        return _pdf_pages(content)
    text = content.decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", text)
    return [(1, " ".join(text.split()))]


def _pdf_pages(content: bytes) -> list[tuple[int, str]]:
    try:
        import pdfplumber
    except ImportError:
        return []
    pages = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((index, text))
    return pages


def _chunks(text: str, size: int = 1200) -> list[str]:
    words = text.split()
    out, buf = [], []
    length = 0
    for word in words:
        buf.append(word)
        length += len(word) + 1
        if length >= size:
            out.append(" ".join(buf))
            buf, length = [], 0
    if buf:
        out.append(" ".join(buf))
    return out
