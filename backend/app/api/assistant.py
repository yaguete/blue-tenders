"""Chat con citas. SSE: cada evento es un JSON y el último es [DONE]."""

import json

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.api.account import current_user
from app.assistant.chat import iter_events, prepare_turn
from app.assistant.documents import prepare
from app.assistant.engine import answer_general
from app.assistant.uploads import store_upload
from app.settings import settings
from app.store import get_store

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _general(question: str, items):
    """Lo usa la evaluación. El chat nuevo pasa por `answer_general` igual."""
    return answer_general(question, items)


def _user(
    authorization: str | None,
    demo: str | None,
    guest: str | None = None,
) -> str:
    """Sin cuentas, un id de navegador basta. Con ASSISTANT_REQUIRES_ACCOUNT=1, hace falta sesión."""
    bearer = (authorization or "").lower().startswith("bearer ")
    if not settings.assistant_requires_account:
        if settings.allow_demo_auth and demo and not bearer:
            return demo[:80]
        return (guest or "guest").strip()[:80] or "guest"
    demo_ok = bool(settings.allow_demo_auth and demo and not bearer)
    if not settings.assistant_public and not demo_ok:
        if authorization or demo:
            raise HTTPException(status_code=403, detail="The assistant is not open to users yet.")
        raise HTTPException(status_code=401, detail="Sign in required")
    return current_user(authorization, demo)


@router.get("/context")
def context(opportunity_id: str) -> dict:
    store = get_store()
    item = store.get(opportunity_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    rows = prepare(store, item, background=True)
    return {
        "opportunity": {
            "id": item.id,
            "title": item.title_en or item.title,
            "url": item.url,
            "programme_id": item.programme_id,
        },
        "documents": [_document(row) for row in rows],
    }


@router.post("/uploads")
async def upload(
    file: UploadFile = File(...),  # noqa: B008  FastAPI lee el fichero de este argumento
    conversation_id: str | None = Form(default=None),
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
    x_assistant_guest: str | None = Header(default=None),
) -> dict:
    user_id = _user(authorization, x_demo_user, x_assistant_guest)
    content = await file.read()
    return store_upload(
        get_store(),
        user_id,
        file.filename or "",
        file.content_type or "",
        content,
        conversation_id,
    )


@router.delete("/uploads/{upload_id}")
def remove_upload(
    upload_id: str,
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
    x_assistant_guest: str | None = Header(default=None),
) -> dict:
    user_id = _user(authorization, x_demo_user, x_assistant_guest)
    store = get_store()
    row = store.upload(upload_id)
    if row is None or row.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Upload not found")
    store.delete_upload(upload_id)
    return {"ok": True}


@router.post("")
def chat(
    body: dict,
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
    x_assistant_guest: str | None = Header(default=None),
) -> StreamingResponse:
    user_id = _user(authorization, x_demo_user, x_assistant_guest)
    turn = prepare_turn(get_store(), user_id, body)

    def stream():
        for event in iter_events(get_store(), turn):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


def _document(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "kind": row.get("kind"),
        "url": row.get("document_url"),
        "access": row.get("access"),
        "status": row.get("status"),
        "pages": row.get("pages") or 0,
        "error": row.get("error"),
        "shared": bool(row.get("shared")),
    }
