from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import account, admin, assistant, catalog_routes, opportunities, tenders
from app.store import FileStore, get_store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store = get_store()
    if isinstance(store, FileStore) and not store.opportunities():
        from app.jobs.seed_demo import build

        build()
    yield


app = FastAPI(title="blue-tender API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://blue-tenders.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(opportunities.router)
app.include_router(catalog_routes.router)
app.include_router(account.router)
app.include_router(assistant.router)
app.include_router(admin.router)
app.include_router(tenders.router)


@app.get("/health")
def health() -> dict:
    freshness = {}
    track_record = {}
    try:
        store = get_store()
        freshness = store.source_freshness()
        track_record = store.track_record_sources()
    except Exception as exc:  # noqa: BLE001  el latido no debe caer si el registro falla
        freshness = {"error": str(exc)}
    return {"ok": True, "sources": freshness, "track_record": track_record}
