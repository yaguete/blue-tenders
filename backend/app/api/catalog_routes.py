"""Directorio de financiadores y subsectores del vertical activo."""

from fastapi import APIRouter

from app.catalog import funder_profiles
from app.vertical import load_vertical

router = APIRouter(tags=["catalog"])


@router.get("/funders")
def funders() -> list[dict]:
    return [item.model_dump() for item in funder_profiles() if item.is_directory_listed]


@router.get("/vertical")
def vertical() -> dict:
    current = load_vertical()
    return {
        "id": current.id,
        "name": current.name,
        "subsectors": [s.model_dump() for s in current.active_subsectors],
    }
