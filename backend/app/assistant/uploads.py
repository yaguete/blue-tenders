"""Subidas del usuario. Se guarda el texto, nunca el fichero. Caducan a las 24 h."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from app.enrich.documents import _pages
from app.models.opportunity import Document

MAX_BYTES = 10 * 1024 * 1024
MAX_PER_CONVERSATION = 3
TTL = timedelta(hours=24)


def accept(filename: str, content_type: str) -> bool:
    low = (filename or "").lower()
    if low.endswith((".pdf", ".txt", ".md")):
        return True
    return content_type in {"application/pdf", "text/plain", "text/markdown"}


def store_upload(store, user_id: str, filename: str, content_type: str, content: bytes, conversation_id: str | None) -> dict:
    store.purge_expired_uploads(datetime.now(UTC))
    if not accept(filename, content_type or ""):
        raise HTTPException(status_code=415, detail="Only PDF and plain text")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 10 MB")
    existing = [
        row
        for row in store.uploads_for_user(user_id)
        if (row.get("conversation_id") or None) == (conversation_id or None)
    ]
    if len(existing) >= MAX_PER_CONVERSATION:
        raise HTTPException(status_code=413, detail="Three files per conversation")
    name = filename or "upload.txt"
    pages = [
        {"page": number, "heading": f"Page {number}", "text": text}
        for number, text in _pages(content, content_type or "", Document(url=name, name=name))
    ]
    pages = [page for page in pages if page["text"].strip()]
    if not pages:
        raise HTTPException(status_code=400, detail="No text in that file")
    upload_id = uuid4().hex
    row = {
        "id": upload_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "name": name,
        "pages": len(pages),
        "expires_at": (datetime.now(UTC) + TTL).isoformat(),
    }
    store.save_upload(row, pages)
    return {"id": upload_id, "name": name, "pages": len(pages), "expires_at": row["expires_at"]}
