from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.catalog import load_default_catalog
from app.db import connect, init_db
from app.ingest import ingest_rows, parse_tabular
from app.search import facets, get_plant, search_plants, stats, suggest

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"


def ensure_seeded() -> None:
    conn = connect()
    try:
        init_db(conn)
        count = conn.execute("SELECT COUNT(*) AS n FROM plants").fetchone()["n"]
    finally:
        conn.close()
    if count == 0:
        load_default_catalog()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_seeded()
    yield


app = FastAPI(title="Woody Plants Search", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats")
def api_stats() -> dict:
    ensure_seeded()
    return stats()


@app.get("/api/search")
def api_search(
    q: str = "",
    family: str = "",
    growth_habit: str = "",
    genus: str = "",
    conservation_status: str = "",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    ensure_seeded()
    return search_plants(
        query=q,
        family=family,
        growth_habit=growth_habit,
        genus=genus,
        conservation_status=conservation_status,
        limit=limit,
        offset=offset,
    )


@app.get("/api/suggest")
def api_suggest(q: str = "", limit: int = Query(default=8, ge=1, le=20)) -> dict:
    ensure_seeded()
    return {"results": suggest(q, limit=limit)}


@app.get("/api/facets")
def api_facets() -> dict:
    ensure_seeded()
    return facets()


@app.get("/api/plants/{plant_id}")
def api_plant(plant_id: int) -> dict:
    plant = get_plant(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant


@app.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    replace: bool = True,
) -> dict:
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith((".csv", ".tsv", ".txt", ".json")):
        raise HTTPException(
            status_code=400,
            detail="Upload a CSV, TSV, TXT, or JSON file",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        headers, rows = parse_tabular(filename, content)
        result = ingest_rows(rows, headers, source_name=filename, replace=replace)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["preview"] = search_plants(query="", limit=5)["results"]
    result["stats"] = stats()
    return result


@app.post("/api/reload-seed")
def reload_seed() -> dict:
    result = load_default_catalog()
    if not result["sources"]:
        raise HTTPException(status_code=404, detail="Seed dataset is missing")
    result["stats"] = stats()
    return result


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
