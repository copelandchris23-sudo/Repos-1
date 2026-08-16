from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SEED_CSV = DATA_DIR / "woody_plants.csv"
DB_PATH = Path(os.environ.get("PLANTS_DB_PATH", DATA_DIR / "plants.db"))

CANONICAL_FIELDS = [
    "scientific_name",
    "synonyms",
    "common_name",
    "family",
    "genus",
    "growth_habit",
    "duration",
    "native_status",
    "category",
    "height_mature_ft",
    "leaf_retention",
    "flower_color",
    "bloom_period",
    "drought_tolerance",
    "shade_tolerance",
    "lifespan",
    "usda_symbol",
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY,
    scientific_name TEXT NOT NULL DEFAULT '',
    synonyms TEXT NOT NULL DEFAULT '',
    common_name TEXT NOT NULL DEFAULT '',
    family TEXT NOT NULL DEFAULT '',
    genus TEXT NOT NULL DEFAULT '',
    growth_habit TEXT NOT NULL DEFAULT '',
    duration TEXT NOT NULL DEFAULT '',
    native_status TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    height_mature_ft TEXT NOT NULL DEFAULT '',
    leaf_retention TEXT NOT NULL DEFAULT '',
    flower_color TEXT NOT NULL DEFAULT '',
    bloom_period TEXT NOT NULL DEFAULT '',
    drought_tolerance TEXT NOT NULL DEFAULT '',
    shade_tolerance TEXT NOT NULL DEFAULT '',
    lifespan TEXT NOT NULL DEFAULT '',
    usda_symbol TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}',
    extra_text TEXT NOT NULL DEFAULT '',
    search_blob TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS plants_fts USING fts5(
    scientific_name,
    synonyms,
    common_name,
    family,
    genus,
    growth_habit,
    extra_text,
    search_blob,
    content='plants',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def reset_plants(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS plants_fts")
    conn.execute("DROP TABLE IF EXISTS plants")
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default
