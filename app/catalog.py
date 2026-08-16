from __future__ import annotations

from pathlib import Path

from app.db import DATA_DIR, SEED_CSV, connect, get_meta, init_db, set_meta
from app.ingest import ingest_file

EXTERNAL_DIR = DATA_DIR / "external"


def catalog_files() -> list[Path]:
    files: list[Path] = []
    if SEED_CSV.exists():
        files.append(SEED_CSV)
    if EXTERNAL_DIR.exists():
        files.extend(sorted(EXTERNAL_DIR.glob("*.csv")))
    return files


def load_default_catalog(db_path: Path | str | None = None) -> dict:
    files = catalog_files()
    if not files:
        return {"count": 0, "sources": []}
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
    conn = connect(db_path)
    try:
        init_db(conn)
        set_meta(conn, "source", " + ".join(sources))
        set_meta(conn, "count", str(conn.execute("SELECT COUNT(*) AS n FROM plants").fetchone()["n"]))
        conn.commit()
        total = int(get_meta(conn, "count", "0") or 0)
    finally:
        conn.close()
    return {"count": total, "added": added, "skipped": skipped, "sources": sources}
