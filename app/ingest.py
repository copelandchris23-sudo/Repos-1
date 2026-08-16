from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Iterable

from app.db import CANONICAL_FIELDS, connect, init_db, reset_plants, set_meta

COLUMN_ALIASES = {
    "scientific_name": {
        "scientific_name",
        "scientific name",
        "latin_name",
        "latin name",
        "binomial",
        "taxon",
        "species",
        "sci_name",
        "accepted name",
        "accepted_name",
        "botanical_name",
        "botanical name",
    },
    "synonyms": {"synonyms", "synonym", "other names", "aka"},
    "common_name": {
        "common_name",
        "common name",
        "common names",
        "vernacular",
        "english name",
        "preferred common name",
        "plant name",
        "name",
    },
    "family": {"family", "plant family", "family_name"},
    "genus": {"genus"},
    "growth_habit": {
        "growth_habit",
        "growth habit",
        "habit",
        "form",
        "growth form",
        "growth_form",
        "ligneous_type",
        "ligneous type",
        "plant type",
        "type",
    },
    "duration": {"duration", "life cycle", "lifecycle"},
    "native_status": {"native_status", "native status", "nativity", "native"},
    "category": {"category", "group", "plant category"},
    "height_mature_ft": {
        "height_mature_ft",
        "height, mature (feet)",
        "height mature ft",
        "mature height",
        "height",
        "height_ft",
        "height (ft)",
    },
    "leaf_retention": {"leaf_retention", "leaf retention", "evergreen", "foliage retention"},
    "flower_color": {"flower_color", "flower color", "flower colour", "bloom color"},
    "bloom_period": {"bloom_period", "bloom period", "flowering period", "bloom time"},
    "drought_tolerance": {"drought_tolerance", "drought tolerance", "drought"},
    "shade_tolerance": {"shade_tolerance", "shade tolerance", "shade"},
    "lifespan": {"lifespan", "life span", "longevity"},
    "usda_symbol": {"usda_symbol", "usda symbol", "accepted symbol", "symbol", "plants symbol"},
}

_ALIAS_LOOKUP = {
    alias: field
    for field, aliases in COLUMN_ALIASES.items()
    for alias in aliases
}


def normalize_header(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def map_headers(headers: Iterable[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used_fields: set[str] = set()
    for header in headers:
        key = normalize_header(header)
        field = _ALIAS_LOOKUP.get(key)
        if field and field not in used_fields:
            mapping[header] = field
            used_fields.add(field)
        else:
            mapping[header] = f"extra:{header}"
    return mapping


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "evergreen"}


def derived_search_terms(record: dict[str, str]) -> list[str]:
    terms: list[str] = []
    habit = record.get("growth_habit", "").lower()
    if "tree" in habit:
        terms.append("tree")
    if "shrub" in habit:
        terms.append("shrub")
    if "subshrub" in habit:
        terms.append("subshrub")
    if "vine" in habit:
        terms.append("vine")

    retention = record.get("leaf_retention", "")
    if _truthy(retention) or retention.strip().lower() == "evergreen":
        terms.extend(["evergreen", "leaf retention yes"])
    elif retention.strip().lower() in {"no", "n", "false", "0", "deciduous"}:
        terms.extend(["deciduous", "leaf retention no"])

    drought = record.get("drought_tolerance", "").strip().lower()
    if drought in {"high", "very high"}:
        terms.append("drought tolerant")
    shade = record.get("shade_tolerance", "").strip().lower()
    if shade in {"high", "tolerant", "very high"}:
        terms.append("shade tolerant")
    elif shade in {"intermediate", "medium"}:
        terms.append("part shade")
    return terms


def record_from_row(row: dict[str, Any], header_map: dict[str, str]) -> dict[str, Any]:
    record = {field: "" for field in CANONICAL_FIELDS}
    extra: dict[str, Any] = {}
    for original, mapped in header_map.items():
        if original not in row:
            continue
        value = row[original]
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if mapped.startswith("extra:"):
            extra[original] = text
        else:
            record[mapped] = text
    if not record["genus"] and record["scientific_name"]:
        record["genus"] = record["scientific_name"].split()[0]
    extra_bits = [f"{key}: {value}" for key, value in extra.items()]
    extra_bits.extend(derived_search_terms(record))
    record["extra_json"] = json.dumps(extra, ensure_ascii=False)
    record["extra_text"] = " | ".join(extra_bits)
    searchable = [
        record[field]
        for field in CANONICAL_FIELDS
        if record[field]
    ]
    searchable.append(record["extra_text"])
    record["search_blob"] = " ".join(searchable)
    return record


def parse_tabular(filename: str, content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    name = filename.lower()
    if name.endswith(".json"):
        payload = json.loads(content.decode("utf-8-sig"))
        if isinstance(payload, dict):
            for key in ("plants", "data", "records", "rows"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
            else:
                payload = [payload]
        if not isinstance(payload, list):
            raise ValueError("JSON upload must be a list of objects")
        rows = [item for item in payload if isinstance(item, dict)]
        headers = sorted({str(key) for row in rows for key in row.keys()})
        return headers, rows

    text = content.decode("utf-8-sig")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("Could not detect column headers")
    headers = [str(h) for h in reader.fieldnames if h]
    rows = [{k: v for k, v in row.items() if k} for row in reader]
    return headers, rows


def insert_records(conn, records: list[dict[str, Any]]) -> None:
    fields = CANONICAL_FIELDS + ["extra_json", "extra_text", "search_blob"]
    placeholders = ", ".join("?" for _ in fields)
    columns = ", ".join(fields)
    last_id = conn.execute("SELECT COALESCE(MAX(id), 0) AS n FROM plants").fetchone()["n"]
    conn.executemany(
        f"INSERT INTO plants ({columns}) VALUES ({placeholders})",
        [tuple(record.get(field, "") for field in fields) for record in records],
    )
    conn.execute(
        """
        INSERT INTO plants_fts(
            rowid, scientific_name, synonyms, common_name, family, genus,
            growth_habit, extra_text, search_blob
        )
        SELECT id, scientific_name, synonyms, common_name, family, genus,
               growth_habit, extra_text, search_blob
        FROM plants
        WHERE id > ?
        """,
        (last_id,),
    )


def ingest_rows(
    rows: list[dict[str, Any]],
    headers: list[str],
    db_path: Path | str | None = None,
    source_name: str = "upload",
    replace: bool = True,
) -> dict[str, Any]:
    header_map = map_headers(headers)
    records = [record_from_row(row, header_map) for row in rows]
    records = [
        record
        for record in records
        if record["scientific_name"] or record["common_name"] or record["genus"]
    ]
    conn = connect(db_path)
    try:
        init_db(conn)
        if replace:
            reset_plants(conn)
        insert_records(conn, records)
        mapped = sorted({field for field in header_map.values() if not field.startswith("extra:")})
        extras = sorted(header[6:] for header in header_map.values() if header.startswith("extra:"))
        set_meta(conn, "source", source_name)
        set_meta(conn, "count", str(len(records)))
        conn.commit()
        return {
            "count": len(records),
            "mapped_columns": mapped,
            "extra_columns": extras,
            "source": source_name,
        }
    finally:
        conn.close()


def ingest_file(path: Path, db_path: Path | str | None = None, replace: bool = True) -> dict[str, Any]:
    content = path.read_bytes()
    headers, rows = parse_tabular(path.name, content)
    return ingest_rows(rows, headers, db_path=db_path, source_name=path.name, replace=replace)
