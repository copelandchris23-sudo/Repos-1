from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from app.db import CANONICAL_FIELDS, connect, get_meta, init_db
from app.filters import FILTER_GROUPS, option_counts, selected_filters, where_clause

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


def _blurb(extra_text: str) -> str:
    for part in extra_text.split(" | "):
        if part.lower().startswith("uses:"):
            return part.split(":", 1)[1].strip()[:220]
    return extra_text[:220]


def _row_to_plant(row: sqlite3.Row, include_extra: bool = False) -> dict[str, Any]:
    plant = {field: row[field] for field in CANONICAL_FIELDS}
    plant["id"] = row["id"]
    plant["blurb"] = _blurb(row["extra_text"] or "")
    if include_extra:
        try:
            plant["extra"] = json.loads(row["extra_json"] or "{}")
        except json.JSONDecodeError:
            plant["extra"] = {}
        plant["extra_text"] = row["extra_text"]
    return plant


def _query_parts(
    query: str,
    selected: dict[str, list[str]],
    *,
    exclude: str | None = None,
) -> tuple[str, str, list[Any]]:
    match = build_match_query(query)
    where, params = where_clause(selected, exclude=exclude)
    join = ""
    if match:
        where = f"{where} AND plants_fts MATCH ?"
        params = [*params, match]
        join = "JOIN plants_fts ON plants_fts.rowid = plants.id"
    return where, join, params


def search_plants(
    query: str,
    family: str = "",
    growth_habit: str = "",
    genus: str = "",
    conservation_status: str = "",
    selected: dict[str, list[str]] | None = None,
    limit: int = 25,
    offset: int = 0,
    db_path: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    chosen = selected_filters(
        selected,
        family=family,
        growth_habit=growth_habit,
        genus=genus,
        conservation_status=conservation_status,
    )
    where, join, params = _query_parts(query, chosen)
    match = build_match_query(query)
    order = (
        "bm25(plants_fts), plants.common_name COLLATE NOCASE"
        if match
        else "plants.genus COLLATE NOCASE, plants.common_name COLLATE NOCASE, plants.scientific_name COLLATE NOCASE"
    )

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
                "filters": chosen,
                "results": [],
            }
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "query": query,
            "filters": chosen,
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


def facets(
    query: str = "",
    selected: dict[str, list[str]] | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    chosen = selected_filters(selected)
    conn = connect(db_path)
    try:
        init_db(conn)
        where, join, params = _query_parts(query, chosen)
        try:
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM plants {join} WHERE {where}",
                params,
            ).fetchone()["n"]
        except sqlite3.OperationalError:
            total = 0
        groups = []
        for group in FILTER_GROUPS:
            group_where, group_join, group_params = _query_parts(query, chosen, exclude=group["key"])
            try:
                options = option_counts(
                    conn,
                    group,
                    group_where,
                    group_params,
                    join=group_join,
                )
            except sqlite3.OperationalError:
                options = [
                    {"value": value, "label": label, "count": 0}
                    for value, label in group.get("options") or []
                ]
            groups.append(
                {
                    "key": group["key"],
                    "label": group["label"],
                    "dynamic": bool(group.get("dynamic")),
                    "options": options,
                }
            )
            selected_values = chosen.get(group["key"]) or []
            present = {item["value"] for item in options}
            for value in selected_values:
                if value not in present:
                    options.insert(0, {"value": value, "label": value, "count": 0})
        return {"total": total, "filters": chosen, "groups": groups}
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
            "sources": [part.strip() for part in get_meta(conn, "source", "").split("+") if part.strip()],
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
