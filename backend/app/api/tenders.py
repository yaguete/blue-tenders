"""Ruta antigua. Redirige a /opportunities."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("")
@router.get("/{tender_id}")
def moved(request: Request, tender_id: str | None = None) -> RedirectResponse:
    path = "/opportunities" if not tender_id else f"/opportunities/{tender_id}"
    if request.url.query:
        path = f"{path}?{request.url.query}"
    return RedirectResponse(path, status_code=308)
