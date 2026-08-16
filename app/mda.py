"""Parse the Minnesota Department of Agriculture Cold Hardiness List HTML.

Source: https://www.mda.state.mn.us/cold-hardiness-list
MDA compiles USDA hardiness ratings for plants sold in Minnesota. The public
page is HTML tables (Excel is available by request). Only woody categories are
kept: shrubs, trees, evergreens, vines, roses, and woody fruit. Perennials,
grasses, and produce are skipped.
"""

from __future__ import annotations

import html as html_lib
import re
from collections import defaultdict
from html.parser import HTMLParser
from typing import Any

MDA_SOURCE = "Minnesota Department of Agriculture Cold Hardiness List"
MDA_URL = "https://www.mda.state.mn.us/cold-hardiness-list"

SKIP_CATEGORIES = {"perennials", "grasses", "produce"}

CATEGORY_HABIT = {
    "shrubs": "Shrub",
    "rose": "Shrub",
    "deciduous (non-fruit)": "Tree",
    "evergreens": "Tree",
    "vines": "Vine",
}

FRUIT_SHRUB_GENERA = {
    "vaccinium",
    "vaccinum",  # MDA spelling of Vaccinium
    "ribes",
    "rubus",
    "lonicera",
    "amelanchier",
    "aronia",
    "sambucus",
    "lycium",
}
FRUIT_VINE_GENERA = {"vitis", "actinidia"}
FRUIT_SKIP_GENERA = {"fragaria"}

SKIP_EPITHETS = {"hybrid", "x", "×", "sp", "spp", "sp.", "spp."}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cell: list[str] = []
        self._row: list[str] = []
        self._table: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._table = []
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._cell = []
        elif self._in_cell and tag == "br":
            self._cell.append(" ")

    def handle_entityref(self, name: str) -> None:
        if self._in_cell:
            self._cell.append(html_lib.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if self._in_cell:
            self._cell.append(html_lib.unescape(f"&#{name};"))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._in_cell:
            text = html_lib.unescape("".join(self._cell)).replace("\xa0", " ")
            self._row.append(re.sub(r"\s+", " ", text).strip())
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            if self._row:
                self._table.append(self._row)
            self._in_row = False
        elif tag == "table" and self._in_table:
            if self._table:
                self.tables.append(self._table)
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell.append(data)


def parse_mda_html(html: str) -> list[dict[str, Any]]:
    parser = _TableParser()
    parser.feed(html)
    rows: list[dict[str, Any]] = []
    for table in parser.tables:
        if not table:
            continue
        header = [cell.lower() for cell in table[0]]
        if "scientific name" not in header or "minimum hardiness zone" not in header:
            continue
        idx = {name: i for i, name in enumerate(header)}
        for raw in table[1:]:
            if len(raw) < len(header):
                raw = raw + [""] * (len(header) - len(raw))
            scientific = raw[idx["scientific name"]].strip()
            zone_raw = raw[idx["minimum hardiness zone"]].strip()
            if not scientific or not zone_raw:
                continue
            category = raw[idx["category"]].strip() if "category" in idx else ""
            common = raw[idx["common name"]].strip() if "common name" in idx else ""
            notes = ""
            for key in idx:
                if "cultivar" in key or "variety" in key or "trade name" in key:
                    notes = raw[idx[key]].strip()
                    break
            rows.append(
                {
                    "category": category,
                    "scientific_name": scientific,
                    "common_name": common,
                    "notes": notes,
                    "zone_raw": zone_raw,
                }
            )
    return rows


def _is_epithet(token: str) -> bool:
    cleaned = token.strip(".,;").lower().rstrip(".")
    if not cleaned or cleaned in SKIP_EPITHETS:
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z-]*$", token.strip(".,;")))


def _normalize_scientific(name: str) -> str | None:
    name = html_lib.unescape(name).replace("\xa0", " ")
    name = re.sub(r"\s+", " ", name).strip()
    name = name.replace(" x ", " × ").replace(" X ", " × ")
    parts = name.split(" ")
    if len(parts) < 2:
        return None
    genus = parts[0].strip(".,;")
    if not genus or not genus[0].isupper() or not re.match(r"^[A-Za-z][A-Za-z-]*$", genus):
        return None
    rest = parts[1:]
    if rest[0] in {"×", "x", "X"}:
        if len(rest) < 2 or not _is_epithet(rest[1]):
            return None
        return f"{genus} × {rest[1].strip('.,;').lower()}"
    epithet = rest[0].strip(".,;")
    if not _is_epithet(epithet):
        return None
    return f"{genus} {epithet}"


def _habit_for(category: str, scientific: str) -> str | None:
    cat = category.strip().lower()
    if cat in SKIP_CATEGORIES:
        return None
    if cat == "fruit":
        genus = scientific.split()[0].lower()
        if genus in FRUIT_SKIP_GENERA:
            return None
        if genus in FRUIT_VINE_GENERA:
            return "Vine"
        if genus in FRUIT_SHRUB_GENERA:
            return "Shrub"
        return "Tree"
    return CATEGORY_HABIT.get(cat)


def _parse_zone(value: str) -> int | None:
    match = re.search(r"(\d{1,2})", value)
    if not match:
        return None
    zone = int(match.group(1))
    if 1 <= zone <= 13:
        return zone
    return None


def aggregate_mda_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "zones": set(),
            "commons": [],
            "habits": set(),
            "categories": set(),
            "evergreen": False,
            "notes": [],
        }
    )
    for raw in raw_rows:
        scientific = _normalize_scientific(raw["scientific_name"])
        if not scientific:
            continue
        habit = _habit_for(raw["category"], scientific)
        if not habit:
            continue
        zone = _parse_zone(raw["zone_raw"])
        if zone is None:
            continue
        bucket = grouped[scientific]
        bucket["zones"].add(zone)
        bucket["habits"].add(habit)
        if raw["category"]:
            bucket["categories"].add(raw["category"])
        if raw["common_name"]:
            bucket["commons"].append(raw["common_name"])
        if raw["notes"]:
            bucket["notes"].append(raw["notes"])
        if raw["category"].strip().lower() == "evergreens":
            bucket["evergreen"] = True

    records: list[dict[str, str]] = []
    for scientific, bucket in grouped.items():
        zones = sorted(bucket["zones"])
        zone_value = str(zones[0]) if len(zones) == 1 else f"{zones[0]}-{zones[-1]}"
        habits = bucket["habits"]
        if len(habits) == 1:
            habit = next(iter(habits))
        elif "Tree" in habits:
            habit = "Tree"
        elif "Shrub" in habits:
            habit = "Shrub"
        else:
            habit = next(iter(habits))
        common = ""
        if bucket["commons"]:
            counts: dict[str, int] = defaultdict(int)
            for name in bucket["commons"]:
                counts[name] += 1
            common = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        record = {
            "scientific_name": scientific,
            "common_name": common,
            "growth_habit": habit,
            "leaf_retention": "Evergreen" if bucket["evergreen"] else "",
            "usda_hardiness_zone": zone_value,
            "catalog_source": MDA_SOURCE,
            "catalog_source_url": MDA_URL,
            "mda_hardiness_zone": zone_value,
            "mda_categories": "; ".join(sorted(bucket["categories"])),
            "mda_cultivar_notes": "; ".join(sorted(set(bucket["notes"]))[:12]),
        }
        records.append(record)
    records.sort(key=lambda row: row["scientific_name"].lower())
    return records
