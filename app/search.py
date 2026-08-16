from __future__ import annotations

import re
import sqlite3
from typing import Any

from app.db import CANONICAL_FIELDS, connect, get_meta, init_db

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def build_match_query(raw: str) -> str | None:
    text = raw.strip()
    if not text:
        return None
    tokens = TOKEN_RE.findall(text)
    if not tokens:
        return None
    parts = []
    for index, token in enumerate(tokens):
        if index == len(tokens) - 1:
            parts.append(f"{token}*")
        else:
            parts.append(token)
    return " AND ".join(parts)


def _row_to_plant(row: sqlite3.Row, include_extra: bool = False) -> dict[str, Any]:
    plant = {field: row[field] for field in CANONICAL_FIELDS}
    plant["id"] = row["id"]
    if include_extra:
        plant["extra_json"] = row["extra_json"]
        plant["extra_text"] = row["extra_text"]
    return plant


def search_plants(
    query: str,
    family: str = "",
    growth_habit: str = "",
    genus: str = "",
    limit: int = 25,
    offset: int = 0,
    db_path: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    match = build_match_query(query)
    filters = ["1=1"]
    params: list[Any] = []
    if match:
        filters.append("plants_fts MATCH ?")
        params.append(match)
    if family:
        filters.append("plants.family = ?")
        params.append(family)
    if genus:
        filters.append("plants.genus = ?")
        params.append(genus)
    if growth_habit:
        filters.append("plants.growth_habit LIKE ?")
        params.append(f"%{growth_habit}%")

    where = " AND ".join(filters)
    order = "bm25(plants_fts), plants.common_name COLLATE NOCASE" if match else "plants.common_name COLLATE NOCASE, plants.scientific_name COLLATE NOCASE"
    join = "JOIN plants_fts ON plants_fts.rowid = plants.id" if match else ""

    conn = connect(db_path)
    try:
        init_db(conn)
        try:
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM plants {join} WHERE {where}",
                params,
            ).fetchone()["n"]
            rows = conn.execute(
                f"""
                SELECT plants.*
                FROM plants
                {join}
                WHERE {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        except sqlite3.OperationalError:
            return {
                "total": 0,
                "limit": limit,
                "offset": offset,
                "query": query,
                "results": [],
            }
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": query,
            "results": [_row_to_plant(row) for row in rows],
        }
    finally:
        conn.close()


def get_plant(plant_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    conn = connect(db_path)
    try:
        init_db(conn)
        row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
        return _row_to_plant(row, include_extra=True) if row else None
    finally:
        conn.close()


def facets(db_path: str | None = None) -> dict[str, list[dict[str, Any]]]:
    conn = connect(db_path)
    try:
        init_db(conn)

        def grouped(column: str) -> list[dict[str, Any]]:
            rows = conn.execute(
                f"""
                SELECT {column} AS value, COUNT(*) AS count
                FROM plants
                WHERE TRIM({column}) != ''
                GROUP BY {column}
                ORDER BY count DESC, value COLLATE NOCASE
                LIMIT 80
                """
            ).fetchall()
            return [{"value": row["value"], "count": row["count"]} for row in rows]

        return {
            "family": grouped("family"),
            "genus": grouped("genus"),
            "growth_habit": grouped("growth_habit"),
        }
    finally:
        conn.close()


def stats(db_path: str | None = None) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        init_db(conn)
        count = conn.execute("SELECT COUNT(*) AS n FROM plants").fetchone()["n"]
        return {
            "count": count,
            "source": get_meta(conn, "source", "none"),
            "fields": CANONICAL_FIELDS,
        }
    finally:
        conn.close()


def suggest(query: str, limit: int = 8, db_path: str | None = None) -> list[dict[str, str]]:
    text = query.strip()
    if len(text) < 2:
        return []
    like = f"%{text}%"
    conn = connect(db_path)
    try:
        init_db(conn)
        rows = conn.execute(
            """
            SELECT id, scientific_name, common_name, family
            FROM plants
            WHERE scientific_name LIKE ? OR common_name LIKE ? OR genus LIKE ?
            ORDER BY
                CASE
                    WHEN common_name LIKE ? THEN 0
                    WHEN scientific_name LIKE ? THEN 1
                    ELSE 2
                END,
                common_name COLLATE NOCASE
            LIMIT ?
            """,
            (like, like, like, f"{text}%", f"{text}%", limit),
        ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "scientific_name": row["scientific_name"],
                "common_name": row["common_name"],
                "family": row["family"],
            }
            for row in rows
        ]
    finally:
        conn.close()
