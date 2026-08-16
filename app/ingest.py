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
        "botanic",
        "botanic name",
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
        "comm_ful",
        "common",
    },
    "family": {"family", "plant family", "family_name"},
    "genus": {"genus", "generic epithet", "generic"},
    "growth_habit": {
        "growth_habit",
        "growth habit",
        "habit",
        "habit (tree, shrub, vine)",
        "form",
        "growth form",
        "growth_form",
        "ligneous_type",
        "ligneous type",
        "plant type",
        "type",
    },
    "duration": {"duration", "life cycle", "lifecycle"},
    "native_status": {
        "native_status",
        "native status",
        "nativity",
        "native",
        "native range",
    },
    "category": {"category", "group", "plant category"},
    "height_mature_ft": {
        "height_mature_ft",
        "height, mature (feet)",
        "height mature ft",
        "mature height",
        "height",
        "height_ft",
        "height (ft)",
        "max height (ft)",
        "max height",
    },
    "leaf_retention": {
        "leaf_retention",
        "leaf retention",
        "evergreen",
        "foliage retention",
        "leaf persistence",
    },
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

HABIT_CODES = {
    "t": "Tree",
    "tree": "Tree",
    "s": "Shrub",
    "shrub": "Shrub",
    "v": "Vine",
    "vine": "Vine",
    "g": "Groundcover",
    "groundcover": "Groundcover",
    "ground cover": "Groundcover",
}

LEAF_CODES = {
    "d": "Deciduous",
    "deciduous": "Deciduous",
    "e": "Evergreen",
    "evergreen": "Evergreen",
}

DROUGHT_CODES = {
    "h": "High",
    "high": "High",
    "very high": "High",
    "yes": "High",
    "tolerant": "High",
    "m": "Medium",
    "medium": "Medium",
    "moderate": "Medium",
    "l": "Low",
    "low": "Low",
    "n": "None",
    "none": "None",
    "no": "None",
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


def title_binomial(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        return ""
    parts = cleaned.split(" ")
    genus = parts[0][:1].upper() + parts[0][1:].lower()
    rest = [part.lower() if part not in {"×", "x"} else "×" for part in parts[1:]]
    return " ".join([genus, *rest]).strip()


def build_scientific_name(record: dict[str, str], extra: dict[str, Any]) -> str:
    botanic = record.get("scientific_name") or extra.get("Botanic") or extra.get("botanic") or ""
    if botanic:
        name = title_binomial(str(botanic))
    else:
        genus = record.get("genus") or extra.get("Generic Epithet") or ""
        hybrid = extra.get("Specific Hybrid Symbol") or ""
        epithet = extra.get("Specific Epithet") or ""
        infra_rank = extra.get("Infraspecific rank") or ""
        infra = extra.get("Infraspecific Epithet") or ""
        pieces = [genus, hybrid, epithet]
        if infra_rank and infra:
            pieces.extend([infra_rank, infra])
        name = title_binomial(" ".join(str(part) for part in pieces if part))
    cultivar = str(extra.get("Cultivar Epithet") or "").strip()
    if cultivar and cultivar.lower() not in name.lower():
        name = f"{name} '{cultivar}'".strip()
    return name


def friendly_common_name(name: str) -> tuple[str, str]:
    if not name:
        return "", ""
    lines = [line.strip() for line in name.splitlines() if line.strip()]
    display = lines[0] if lines else ""
    notes = " ".join(lines[1:])
    if (
        display.count(",") == 1
        and "'" not in display
        and "’" not in display
        and " - " not in display
    ):
        left, right = [part.strip() for part in display.split(",", 1)]
        if left and right and len(left.split()) <= 3 and len(right.split()) <= 4:
            display = f"{right} {left}"
    return display, notes


def normalize_habit(value: str) -> str:
    if not value:
        return ""
    lower = value.lower()
    found: list[str] = []
    for token, label in (
        ("tree", "Tree"),
        ("shrub", "Shrub"),
        ("vine", "Vine"),
        ("groundcover", "Groundcover"),
        ("ground cover", "Groundcover"),
    ):
        if token in lower:
            found.append(label)
    if found:
        return ", ".join(dict.fromkeys(found))
    codes: list[str] = []
    for part in re.split(r"[,/;]+", value):
        label = HABIT_CODES.get(part.strip().lower())
        if label:
            codes.append(label)
    return ", ".join(dict.fromkeys(codes)) if codes else value


def normalize_coded(value: str, table: dict[str, str]) -> str:
    if not value:
        return ""
    return table.get(value.strip().lower(), value.strip())


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "evergreen", "e"}


def derived_search_terms(record: dict[str, str], extra: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    habit = record.get("growth_habit", "").lower()
    for token in ("tree", "shrub", "subshrub", "vine", "groundcover"):
        if token in habit:
            terms.append(token)

    retention = record.get("leaf_retention", "")
    if _truthy(retention) or retention.strip().lower() in {"evergreen", "e"}:
        terms.append("evergreen")
    elif retention.strip().lower() in {"no", "n", "false", "0", "deciduous", "d"}:
        terms.append("deciduous")

    drought = record.get("drought_tolerance", "").strip().lower()
    if drought in {"high", "h", "very high", "tolerant", "yes"}:
        terms.append("drought tolerant")

    shade = record.get("shade_tolerance", "").strip().lower()
    light = str(extra.get("Light exposure") or extra.get("light exposure") or "").lower()
    if shade in {"high", "tolerant", "very high"} or (light and "shade" in light and "sun" not in light):
        terms.append("shade tolerant")
    elif "sun" in light and "shade" not in light:
        terms.append("full sun")
    elif "partial" in light or "part shade" in light:
        terms.append("part shade")

    zone = str(extra.get("USDA Hardiness Zone") or extra.get("usda hardiness zone") or "").strip()
    if zone:
        terms.append(f"zone {zone}")
        terms.append(f"hardiness zone {zone}")

    if str(extra.get("Ornamental Winners") or "").strip() in {"*", "yes", "Y"}:
        terms.append("ornamental")
    if str(extra.get("Agricultural Winners") or "").strip() in {"*", "yes", "Y"}:
        terms.append("agricultural")
    nfixer = str(extra.get("Nitrogen-fixer?") or extra.get("Nitrogen-fixer") or "").strip().lower()
    if nfixer in {"y", "yes", "true", "*"}:
        terms.append("nitrogen fixer")
    edible = str(extra.get("Edible?") or extra.get("Edible") or "").strip().lower()
    if edible in {"y", "yes", "true", "*"}:
        terms.append("edible")
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

    record["scientific_name"] = build_scientific_name(record, extra)
    common, common_notes = friendly_common_name(record.get("common_name", ""))
    record["common_name"] = common
    if common_notes:
        extra["common_name_notes"] = common_notes
    record["growth_habit"] = normalize_habit(record.get("growth_habit", ""))
    record["leaf_retention"] = normalize_coded(record.get("leaf_retention", ""), LEAF_CODES)
    record["drought_tolerance"] = normalize_coded(record.get("drought_tolerance", ""), DROUGHT_CODES)
    if not record["genus"] and record["scientific_name"]:
        record["genus"] = record["scientific_name"].split()[0]

    extra_bits = [f"{key}: {value}" for key, value in extra.items()]
    extra_bits.extend(derived_search_terms(record, extra))
    record["extra_json"] = json.dumps(extra, ensure_ascii=False)
    record["extra_text"] = " | ".join(extra_bits)
    searchable = [record[field] for field in CANONICAL_FIELDS if record[field]]
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
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    raw_rows = list(csv.reader(io.StringIO(text), dialect=dialect))
    while raw_rows and not any(cell.strip() for cell in raw_rows[0]):
        raw_rows.pop(0)
    if not raw_rows:
        raise ValueError("Could not detect column headers")

    seen: dict[str, int] = {}
    headers: list[str] = []
    for index, header in enumerate(raw_rows[0]):
        label = (header or "").strip() or f"column_{index + 1}"
        if label in seen:
            seen[label] += 1
            label = f"{label}_{seen[label]}"
        else:
            seen[label] = 1
        headers.append(label)

    rows: list[dict[str, Any]] = []
    for raw in raw_rows[1:]:
        if not any(cell.strip() for cell in raw):
            continue
        padded = list(raw) + [""] * (len(headers) - len(raw))
        rows.append({headers[i]: padded[i] for i in range(len(headers))})
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
        extras = sorted(
            header[6:] for header in header_map.values() if header.startswith("extra:")
        )
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
