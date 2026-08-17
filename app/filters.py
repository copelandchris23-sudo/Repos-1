"""Identification-style checkbox filters, in the spirit of OSU Landscape Plants.

Selecting a characteristic keeps plants that have it and drops the rest. Several
values in the same group are combined with OR; different groups are combined
with AND. Facet counts ignore the group they belong to so extra options stay
selectable.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from app.ingest import THREATENED_STATUSES

CONIFER_FAMILIES = {
    "pinaceae",
    "cupressaceae",
    "taxaceae",
    "araucariaceae",
    "podocarpaceae",
    "sciadopityaceae",
    "cephalotaxaceae",
    "taxodiaceae",
    "ginkgoaceae",
    "cycadaceae",
    "zamiaceae",
    "ephedraceae",
    "welwitschiaceae",
    "gnetaceae",
}

FLOWER_COLORS = (
    ("white", "White/gray", ("white", "gray", "grey", "cream", "ivory")),
    ("yellow", "Yellow", ("yellow", "gold")),
    ("pink", "Pink", ("pink",)),
    ("red", "Red", ("red", "crimson", "scarlet")),
    ("orange", "Orange", ("orange",)),
    ("purple", "Purple/violet", ("purple", "violet", "lavender", "magenta", "indigo", "lilac")),
    ("blue", "Blue", ("blue",)),
    ("green", "Green", ("green",)),
    ("brown", "Brown", ("brown",)),
)

BLOOM_SEASONS = (
    ("spring", "Spring", ("spring", "esp", "msp", "lsp", "sp")),
    ("summer", "Summer", ("summer", "esu", "msu", "lsu", "su")),
    ("fall", "Fall", ("fall", "autumn", "efa", "mfa", "lfa")),
    ("winter", "Winter", ("winter", "ewi", "mwi", "lwi", "wi")),
)

HEIGHT_BUCKETS = (
    ("under-15", "Under 15 ft", 0.0, 15.0),
    ("15-40", "15–40 ft", 15.0, 40.0),
    ("40-80", "40–80 ft", 40.0, 80.0),
    ("80-plus", "80 ft or taller", 80.0, None),
)

HARDINESS_ZONES = [str(zone) for zone in range(1, 12)]

FILTER_GROUPS = (
    {
        "key": "foliage_type",
        "label": "Leaf type",
        "options": (
            ("broadleaf", "Woody broadleaf"),
            ("conifer", "Woody conifer"),
        ),
    },
    {
        "key": "growth_habit",
        "label": "Growth habit",
        "options": (
            ("Tree", "Tree"),
            ("Shrub", "Shrub"),
            ("Vine", "Vine"),
            ("Groundcover", "Groundcover"),
        ),
    },
    {
        "key": "leaf_retention",
        "label": "Leaf persistence",
        "options": (
            ("Evergreen", "Evergreen"),
            ("Deciduous", "Deciduous"),
        ),
    },
    {
        "key": "hardiness_zone",
        "label": "USDA hardiness zone",
        "options": tuple((zone, f"Zone {zone}") for zone in HARDINESS_ZONES),
    },
    {
        "key": "height",
        "label": "Mature height",
        "options": tuple((key, label) for key, label, _lo, _hi in HEIGHT_BUCKETS),
    },
    {
        "key": "flower_color",
        "label": "Flower color",
        "options": tuple((key, label) for key, label, _tokens in FLOWER_COLORS),
    },
    {
        "key": "bloom_period",
        "label": "Bloom season",
        "options": tuple((key, label) for key, label, _tokens in BLOOM_SEASONS),
    },
    {
        "key": "light",
        "label": "Light",
        "options": (
            ("sun", "Full sun"),
            ("part-shade", "Part shade"),
            ("shade", "Shade"),
        ),
    },
    {
        "key": "drought_tolerance",
        "label": "Drought tolerance",
        "options": (
            ("High", "High"),
            ("Medium", "Medium"),
            ("Low", "Low"),
        ),
    },
    {
        "key": "conservation_status",
        "label": "Conservation",
        "options": (
            ("threatened", "Threatened"),
            ("Near Threatened", "Near Threatened"),
            ("Least Concern", "Least Concern"),
            ("Data Deficient", "Data Deficient"),
        ),
    },
    {
        "key": "thin_barked",
        "label": "Bark",
        "options": (("Yes", "Thin-barked"),),
    },
    {
        "key": "coarse_roots",
        "label": "Roots",
        "options": (("Yes", "Coarse roots"),),
    },
    {
        "key": "production_method",
        "label": "Production method",
        "options": (
            ("Container", "Container"),
            ("In-ground", "In-ground"),
        ),
    },
    {
        "key": "planting_season",
        "label": "Planting season",
        "options": (
            ("Spring", "Spring"),
            ("Fall", "Fall"),
        ),
    },
    {
        "key": "family",
        "label": "Family",
        "options": (),
        "dynamic": True,
    },
)

FILTER_KEYS = tuple(group["key"] for group in FILTER_GROUPS)

_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")
_ZONE_RE = re.compile(r"(\d{1,2})")


def as_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    return [str(part).strip() for part in value if str(part).strip()]


def selected_filters(
    values: dict[str, str | Iterable[str] | None] | None = None,
    **legacy: str | Iterable[str] | None,
) -> dict[str, list[str]]:
    combined = dict(values or {})
    for key, value in legacy.items():
        if value and key not in combined:
            combined[key] = value
    selected: dict[str, list[str]] = {}
    for key, value in combined.items():
        if key not in FILTER_KEYS and key != "genus":
            continue
        items = as_list(value)
        if items:
            selected[key] = items
    return selected


def zone_bounds(value: str) -> tuple[int, int] | None:
    zones = [int(match) for match in _ZONE_RE.findall(value or "") if 1 <= int(match) <= 13]
    if not zones:
        return None
    return min(zones), max(zones)


def zone_min(value: str) -> int | None:
    bounds = zone_bounds(value)
    return bounds[0] if bounds else None


def zone_max(value: str) -> int | None:
    bounds = zone_bounds(value)
    return bounds[1] if bounds else None


def height_num(value: str) -> float | None:
    match = _NUMBER_RE.search(value or "")
    if not match:
        return None
    number = float(match.group(1))
    if number <= 0:
        return None
    return number


def is_conifer(family: str) -> int:
    return 1 if (family or "").strip().lower() in CONIFER_FAMILIES else 0


def json_field(blob: str, key: str) -> str:
    try:
        extra = json.loads(blob or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(extra, dict):
        return ""
    value = extra.get(key)
    return str(value).strip() if value else ""


def _contains_token(text: str, token: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", text) is not None


def flower_has(color: str, wanted: str) -> int:
    text = (color or "").lower()
    if not text:
        return 0
    for key, _label, tokens in FLOWER_COLORS:
        if key == wanted and any(_contains_token(text, token) for token in tokens):
            return 1
    return 0


def bloom_has(period: str, wanted: str) -> int:
    text = re.sub(r"[^a-z]", "", (period or "").lower())
    if not text:
        return 0
    for key, _label, tokens in BLOOM_SEASONS:
        if key != wanted:
            continue
        for token in tokens:
            compact = re.sub(r"[^a-z]", "", token)
            if compact and compact in text:
                return 1
    return 0


def light_has(shade_tolerance: str, extra_json: str, wanted: str) -> int:
    extra = json_field(extra_json, "Light exposure") or json_field(extra_json, "light exposure")
    text = f"{shade_tolerance or ''} {extra}".lower()
    if not text.strip():
        return 0
    found: set[str] = set()
    if "intolerant" in text or "full sun" in text or re.search(r"(^|[\s,;/])(full|sun)([\s,;/]|$)", text):
        found.add("sun")
    if "intermediate" in text or "partial" in text or "part shade" in text or "part-shade" in text:
        found.add("part-shade")
    if re.search(r"(^|[^a-z])tolerant\b", text) and "intolerant" not in text:
        found.add("shade")
    if re.search(r"(^|[\s,;/])shade([\s,;/]|$)", text):
        found.add("shade")
    if "sun/partial" in text or "sun to part" in text or "full sun part shade" in text:
        found.add("sun")
        found.add("part-shade")
    return 1 if wanted in found else 0


def leaf_has(value: str, wanted: str) -> int:
    text = (value or "").strip().lower()
    if wanted == "Evergreen":
        return 1 if text in {"evergreen", "e", "yes", "y"} else 0
    if wanted == "Deciduous":
        return 1 if text in {"deciduous", "d", "no", "n"} else 0
    return 0


def height_has(value: str, wanted: str) -> int:
    number = height_num(value)
    if number is None:
        return 0
    for key, _label, low, high in HEIGHT_BUCKETS:
        if key != wanted:
            continue
        if number < low:
            return 0
        if high is None:
            return 1
        return 1 if number < high else 0
    return 0


def zone_has(value: str, wanted: str) -> int:
    try:
        zone = int(wanted)
    except ValueError:
        return 0
    bounds = zone_bounds(value)
    if not bounds:
        return 0
    return 1 if bounds[0] <= zone <= bounds[1] else 0


def conservation_has(value: str, wanted: str) -> int:
    text = (value or "").strip()
    if not text:
        return 0
    if wanted.lower() == "threatened":
        return 1 if any(text == status or text.startswith(status) for status in THREATENED_STATUSES) else 0
    return 1 if text == wanted or text.startswith(wanted) else 0


def register_functions(conn) -> None:
    helpers = (
        ("zone_min", 1, zone_min),
        ("zone_max", 1, zone_max),
        ("height_num", 1, height_num),
        ("is_conifer", 1, is_conifer),
        ("json_field", 2, json_field),
        ("flower_has", 2, flower_has),
        ("bloom_has", 2, bloom_has),
        ("light_has", 3, light_has),
        ("leaf_has", 2, leaf_has),
        ("height_has", 2, height_has),
        ("zone_has", 2, zone_has),
        ("conservation_has", 2, conservation_has),
    )
    for name, nargs, func in helpers:
        try:
            conn.create_function(name, nargs, func, deterministic=True)
        except TypeError:
            conn.create_function(name, nargs, func)


def _or_clause(fragments: list[str]) -> str:
    if not fragments:
        return "1=1"
    if len(fragments) == 1:
        return fragments[0]
    return "(" + " OR ".join(fragments) + ")"


def clause_for(key: str, values: list[str]) -> tuple[str, list[Any]]:
    values = [value for value in values if value]
    if not values:
        return "1=1", []
    if key == "growth_habit":
        return _or_clause(["plants.growth_habit LIKE ?" for _ in values]), [f"%{value}%" for value in values]
    if key == "family":
        placeholders = ", ".join("?" for _ in values)
        return f"plants.family IN ({placeholders})", values
    if key == "genus":
        return "plants.genus = ?", [values[0]]
    if key == "foliage_type":
        parts: list[str] = []
        params: list[Any] = []
        if "conifer" in values:
            parts.append("is_conifer(plants.family) = 1")
        if "broadleaf" in values:
            parts.append("(TRIM(plants.family) != '' AND is_conifer(plants.family) = 0)")
        return _or_clause(parts), params
    if key == "leaf_retention":
        return _or_clause(["leaf_has(plants.leaf_retention, ?) = 1" for _ in values]), values
    if key == "hardiness_zone":
        return _or_clause(["zone_has(plants.usda_hardiness_zone, ?) = 1" for _ in values]), values
    if key == "height":
        return _or_clause(["height_has(plants.height_mature_ft, ?) = 1" for _ in values]), values
    if key == "flower_color":
        return _or_clause(["flower_has(plants.flower_color, ?) = 1" for _ in values]), values
    if key == "bloom_period":
        return _or_clause(["bloom_has(plants.bloom_period, ?) = 1" for _ in values]), values
    if key == "drought_tolerance":
        return _or_clause(["plants.drought_tolerance = ?" for _ in values]), values
    if key == "light":
        return (
            _or_clause(["light_has(plants.shade_tolerance, plants.extra_json, ?) = 1" for _ in values]),
            values,
        )
    if key == "conservation_status":
        return _or_clause(["conservation_has(plants.conservation_status, ?) = 1" for _ in values]), values
    if key == "thin_barked":
        return _or_clause(["LOWER(TRIM(plants.thin_barked)) = ?" for _ in values]), [value.lower() for value in values]
    if key == "coarse_roots":
        return _or_clause(["LOWER(TRIM(plants.coarse_roots)) = ?" for _ in values]), [value.lower() for value in values]
    if key == "production_method":
        likes = []
        params: list[Any] = []
        for value in values:
            if value.lower() == "container":
                likes.append("LOWER(plants.production_method) LIKE ?")
                params.append("%container%")
            elif value.lower() in {"in-ground", "in ground"}:
                likes.append("(LOWER(plants.production_method) LIKE ? OR LOWER(plants.production_method) LIKE ?)")
                params.extend(["%in-ground%", "%in ground%"])
            else:
                likes.append("plants.production_method = ?")
                params.append(value)
        return _or_clause(likes), params
    if key == "planting_season":
        return _or_clause(["plants.planting_season = ?" for _ in values]), values
    return "1=1", []


def where_clause(
    selected: dict[str, list[str]],
    *,
    exclude: str | None = None,
) -> tuple[str, list[Any]]:
    fragments = ["1=1"]
    params: list[Any] = []
    for key, values in selected.items():
        if key == exclude:
            continue
        sql, extra = clause_for(key, values)
        if sql != "1=1":
            fragments.append(sql)
            params.extend(extra)
    return " AND ".join(fragments), params


def option_counts(
    conn,
    group: dict[str, Any],
    where: str,
    params: list[Any],
    join: str = "",
) -> list[dict[str, Any]]:
    key = group["key"]
    from_clause = f"plants {join}".strip()
    if group.get("dynamic"):
        rows = conn.execute(
            f"""
            SELECT family AS value, COUNT(*) AS count
            FROM {from_clause}
            WHERE {where} AND TRIM(plants.family) != ''
            GROUP BY plants.family
            ORDER BY count DESC, plants.family COLLATE NOCASE
            LIMIT 80
            """,
            params,
        ).fetchall()
        return [{"value": row["value"], "label": row["value"], "count": row["count"]} for row in rows]

    if key == "hardiness_zone":
        rows = conn.execute(
            f"""
            SELECT plants.usda_hardiness_zone AS value, COUNT(*) AS count
            FROM {from_clause}
            WHERE {where} AND TRIM(plants.usda_hardiness_zone) != ''
            GROUP BY plants.usda_hardiness_zone
            """,
            params,
        ).fetchall()
        tallies = {zone: 0 for zone in HARDINESS_ZONES}
        for row in rows:
            bounds = zone_bounds(row["value"])
            if not bounds:
                continue
            for zone in range(bounds[0], bounds[1] + 1):
                label = str(zone)
                if label in tallies:
                    tallies[label] += row["count"]
        return [{"value": zone, "label": f"Zone {zone}", "count": tallies[zone]} for zone in HARDINESS_ZONES]

    selects = []
    option_params: list[Any] = []
    for index, (value, _label) in enumerate(group["options"]):
        sql, extra = clause_for(key, [value])
        selects.append(f"SUM(CASE WHEN {sql} THEN 1 ELSE 0 END) AS c{index}")
        option_params.extend(extra)
    row = conn.execute(
        f"SELECT {', '.join(selects)} FROM {from_clause} WHERE {where}",
        [*option_params, *params],
    ).fetchone()
    return [
        {"value": value, "label": label, "count": int(row[f"c{index}"] or 0)}
        for index, (value, label) in enumerate(group["options"])
    ]
