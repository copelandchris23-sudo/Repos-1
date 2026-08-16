from __future__ import annotations

from pathlib import Path

from app.db import DATA_DIR, SEED_CSV, connect, get_meta, init_db, set_meta
from app.ingest import enrich_empty_fields, ingest_file, lookup_from_csv

EXTERNAL_DIR = DATA_DIR / "external"
OVERLAY_ONLY = {"iucn_conservation_status.csv"}

ARNOLD_ENRICH_FIELDS = [
    "growth_habit",
    "common_name",
    "family",
    "genus",
    "synonyms",
    "height_mature_ft",
]
IUCN_ENRICH_FIELDS = [
    "conservation_status",
    "family",
    "genus",
    "growth_habit",
]
TSO_ENRICH_FIELDS = [
    "usda_hardiness_zone",
    "height_mature_ft",
    "native_status",
    "common_name",
    "family",
    "genus",
    "synonyms",
]
MDA_ENRICH_FIELDS = [
    "usda_hardiness_zone",
    "growth_habit",
    "common_name",
    "leaf_retention",
]


def catalog_files() -> list[Path]:
    files: list[Path] = []
    if SEED_CSV.exists():
        files.append(SEED_CSV)
    if EXTERNAL_DIR.exists():
        files.extend(
            path
            for path in sorted(EXTERNAL_DIR.glob("*.csv"))
            if path.name not in OVERLAY_ONLY
        )
    return files


def _enrich_from(path: Path, fields: list[str], db_path: Path | str | None) -> dict:
    if not path.exists():
        return {"updated": 0, "source": path.name, "missing": True}
    lookup = lookup_from_csv(path)
    result = enrich_empty_fields(lookup, fields, db_path=db_path)
    result["source"] = path.name
    return result


def load_default_catalog(db_path: Path | str | None = None) -> dict:
    files = catalog_files()
    if not files:
        return {"count": 0, "sources": [], "enriched": []}
    first = True
    sources: list[str] = []
    added = 0
    skipped = 0
    for path in files:
        result = ingest_file(
            path,
            db_path=db_path,
            replace=first,
            skip_existing=not first,
        )
        first = False
        sources.append(path.name)
        added += int(result.get("count") or 0)
        skipped += int(result.get("skipped") or 0)
    enriched = [
        _enrich_from(EXTERNAL_DIR / "arnold_arboretum_inventory.csv", ARNOLD_ENRICH_FIELDS, db_path),
        _enrich_from(EXTERNAL_DIR / "iucn_conservation_status.csv", IUCN_ENRICH_FIELDS, db_path),
        _enrich_from(EXTERNAL_DIR / "mda_cold_hardiness.csv", MDA_ENRICH_FIELDS, db_path),
        _enrich_from(EXTERNAL_DIR / "trees_and_shrubs_online.csv", TSO_ENRICH_FIELDS, db_path),
    ]
    conn = connect(db_path)
    try:
        init_db(conn)
        set_meta(conn, "source", " + ".join(sources))
        set_meta(conn, "count", str(conn.execute("SELECT COUNT(*) AS n FROM plants").fetchone()["n"]))
        conn.commit()
        total = int(get_meta(conn, "count", "0") or 0)
    finally:
        conn.close()
    return {
        "count": total,
        "added": added,
        "skipped": skipped,
        "sources": sources,
        "enriched": enriched,
    }
