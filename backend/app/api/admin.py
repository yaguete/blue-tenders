"""Cola de revisión. Cabecera X-Admin-Token igual a ADMIN_TOKEN."""

from fastapi import APIRouter, Header, HTTPException

from app.store import get_store

router = APIRouter(prefix="/admin", tags=["admin"])


def _auth(token: str | None) -> None:
    from app.settings import settings

    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Admin token required")


@router.get("/review")
def queue(x_admin_token: str | None = Header(default=None)) -> list[dict]:
    _auth(x_admin_token)
    return [row for row in get_store().load()["reviews"] if not row.get("resolved")]


@router.post("/review/{item_id}/resolve")
def resolve(item_id: str, x_admin_token: str | None = Header(default=None)) -> dict:
    _auth(x_admin_token)
    store = get_store()
    data = store.load()
    found = False
    for row in data["reviews"]:
        if row.get("id") == item_id:
            row["resolved"] = True
            found = True
    if not found:
        raise HTTPException(status_code=404, detail="Review item not found")
    store.save(data)
    return {"ok": True}
