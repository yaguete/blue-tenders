"""Perfil, guardados, alertas y borrado. La búsqueda no pasa por aquí.

Sin Supabase, solo responde si llega `X-Demo-User` y ALLOW_DEMO_AUTH=1.
Eso existe para la demo local, no para producción.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.alerts.send import token_matches, unsubscribe_token
from app.settings import settings
from app.store import get_store

router = APIRouter(tags=["account"])


def current_user(
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
) -> str:
    if settings.supabase_url and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            from supabase import create_client

            client = create_client(settings.supabase_url, settings.supabase_service_role_key)
            user = client.auth.get_user(token)
            if user and user.user:
                return user.user.id
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid session") from exc
    if settings.allow_demo_auth and x_demo_user:
        return x_demo_user[:80]
    raise HTTPException(status_code=401, detail="Sign in required")


def _secret() -> str:
    return settings.admin_token or "dev-unsubscribe-secret"


@router.get("/me")
def me(user: str = Header(default=None, alias="X-Demo-User"), authorization: str | None = Header(default=None)) -> dict:
    uid = current_user(authorization, user)
    data = get_store().load()
    profile = next((row for row in data["profiles"] if row.get("user_id") == uid), None)
    return {"user_id": uid, "profile": profile}


@router.put("/me/profile")
def save_profile(body: dict, authorization: str | None = Header(default=None), x_demo_user: str | None = Header(default=None)) -> dict:
    uid = current_user(authorization, x_demo_user)
    allowed = {"entity_type", "country", "subsectors", "size", "trl", "role", "pic", "name"}
    profile = {key: body.get(key) for key in allowed}
    profile["user_id"] = uid
    store = get_store()
    data = store.load()
    data["profiles"] = [row for row in data["profiles"] if row.get("user_id") != uid]
    data["profiles"].append(profile)
    store.save(data)
    return profile


@router.post("/saved/{opportunity_id}")
def save_opportunity(opportunity_id: str, authorization: str | None = Header(default=None), x_demo_user: str | None = Header(default=None)) -> dict:
    uid = current_user(authorization, x_demo_user)
    if get_store().get(opportunity_id) is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    store = get_store()
    data = store.load()
    data["saved"] = [row for row in data["saved"] if not (row.get("user_id") == uid and row.get("opportunity_id") == opportunity_id)]
    data["saved"].append({"user_id": uid, "opportunity_id": opportunity_id, "at": datetime.now(UTC).isoformat()})
    store.save(data)
    return {"ok": True}


@router.get("/saved")
def list_saved(authorization: str | None = Header(default=None), x_demo_user: str | None = Header(default=None)) -> list[dict]:
    uid = current_user(authorization, x_demo_user)
    return [row for row in get_store().load()["saved"] if row.get("user_id") == uid]


@router.post("/alerts")
def create_alert(body: dict, request: Request, authorization: str | None = Header(default=None), x_demo_user: str | None = Header(default=None)) -> dict:
    uid = current_user(authorization, x_demo_user)
    email = (body.get("email") or "").strip()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Email required")
    alert_id = uuid4().hex[:12]
    token = unsubscribe_token(alert_id, _secret())
    row = {
        "id": alert_id,
        "user_id": uid,
        "email": email,
        "filters": body.get("filters") or {},
        "cadence": body.get("cadence") if body.get("cadence") in {"daily", "weekly"} else "weekly",
        "consent_at": datetime.now(UTC).isoformat(),
        "last_sent_at": None,
        "unsubscribe_token": token,
    }
    store = get_store()
    data = store.load()
    data["alerts"].append(row)
    store.save(data)
    base = str(request.base_url).rstrip("/")
    return {"id": alert_id, "unsubscribe_url": f"{base}/alerts/unsubscribe?id={alert_id}&token={token}"}


@router.get("/alerts/unsubscribe", response_class=PlainTextResponse)
def unsubscribe(id: str, token: str) -> str:
    if not token_matches(id, token, _secret()):
        raise HTTPException(status_code=400, detail="Invalid unsubscribe link")
    store = get_store()
    data = store.load()
    data["alerts"] = [row for row in data["alerts"] if row.get("id") != id]
    data["suppressions"].append({"id": id, "at": datetime.now(UTC).isoformat()})
    store.save(data)
    return "You are unsubscribed. You will not receive further alerts for that search."


@router.get("/me/export")
def export_me(authorization: str | None = Header(default=None), x_demo_user: str | None = Header(default=None)) -> dict:
    uid = current_user(authorization, x_demo_user)
    data = get_store().load()
    return {
        "profile": [row for row in data["profiles"] if row.get("user_id") == uid],
        "saved": [row for row in data["saved"] if row.get("user_id") == uid],
        "alerts": [row for row in data["alerts"] if row.get("user_id") == uid],
        "conversations": [row for row in data["conversations"] if row.get("user_id") == uid],
        "assistant_messages": get_store().messages_for_user(uid),
        "assistant_uploads": [
            {**row, "pages": get_store().upload_pages(row["id"])}
            for row in get_store().uploads_for_user(uid)
        ],
    }


@router.delete("/me")
def delete_me(authorization: str | None = Header(default=None), x_demo_user: str | None = Header(default=None)) -> dict:
    uid = current_user(authorization, x_demo_user)
    store = get_store()
    data = store.load()
    for key in ("profiles", "saved", "alerts", "conversations", "usage"):
        data[key] = [row for row in data[key] if row.get("user_id") != uid]
    store.save(data)
    store.delete_user_assistant(uid)
    return {"ok": True}
