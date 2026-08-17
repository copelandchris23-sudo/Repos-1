from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.catalog import load_default_catalog
from app.db import connect, init_db
from app.ingest import ingest_rows, parse_tabular
from app.filters import selected_filters
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
    family: list[str] = Query(default=[]),
    growth_habit: list[str] = Query(default=[]),
    genus: str = "",
    conservation_status: list[str] = Query(default=[]),
    foliage_type: list[str] = Query(default=[]),
    leaf_retention: list[str] = Query(default=[]),
    hardiness_zone: list[str] = Query(default=[]),
    height: list[str] = Query(default=[]),
    flower_color: list[str] = Query(default=[]),
    bloom_period: list[str] = Query(default=[]),
    drought_tolerance: list[str] = Query(default=[]),
    light: list[str] = Query(default=[]),
    thin_barked: list[str] = Query(default=[]),
    coarse_roots: list[str] = Query(default=[]),
    production_method: list[str] = Query(default=[]),
    planting_season: list[str] = Query(default=[]),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    ensure_seeded()
    selected = selected_filters(
        {
            "family": family,
            "growth_habit": growth_habit,
            "genus": genus,
            "conservation_status": conservation_status,
            "foliage_type": foliage_type,
            "leaf_retention": leaf_retention,
            "hardiness_zone": hardiness_zone,
            "height": height,
            "flower_color": flower_color,
            "bloom_period": bloom_period,
            "drought_tolerance": drought_tolerance,
            "light": light,
            "thin_barked": thin_barked,
            "coarse_roots": coarse_roots,
            "production_method": production_method,
            "planting_season": planting_season,
        }
    )
    return search_plants(
        query=q,
        selected=selected,
        genus=genus,
        limit=limit,
        offset=offset,
    )


@app.get("/api/suggest")
def api_suggest(q: str = "", limit: int = Query(default=8, ge=1, le=20)) -> dict:
    ensure_seeded()
    return {"results": suggest(q, limit=limit)}


@app.get("/api/facets")
def api_facets(
    q: str = "",
    family: list[str] = Query(default=[]),
    growth_habit: list[str] = Query(default=[]),
    genus: str = "",
    conservation_status: list[str] = Query(default=[]),
    foliage_type: list[str] = Query(default=[]),
    leaf_retention: list[str] = Query(default=[]),
    hardiness_zone: list[str] = Query(default=[]),
    height: list[str] = Query(default=[]),
    flower_color: list[str] = Query(default=[]),
    bloom_period: list[str] = Query(default=[]),
    drought_tolerance: list[str] = Query(default=[]),
    light: list[str] = Query(default=[]),
    thin_barked: list[str] = Query(default=[]),
    coarse_roots: list[str] = Query(default=[]),
    production_method: list[str] = Query(default=[]),
    planting_season: list[str] = Query(default=[]),
) -> dict:
    ensure_seeded()
    selected = selected_filters(
        {
            "family": family,
            "growth_habit": growth_habit,
            "genus": genus,
            "conservation_status": conservation_status,
            "foliage_type": foliage_type,
            "leaf_retention": leaf_retention,
            "hardiness_zone": hardiness_zone,
            "height": height,
            "flower_color": flower_color,
            "bloom_period": bloom_period,
            "drought_tolerance": drought_tolerance,
            "light": light,
            "thin_barked": thin_barked,
            "coarse_roots": coarse_roots,
            "production_method": production_method,
            "planting_season": planting_season,
        }
    )
    return facets(query=q, selected=selected)


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
