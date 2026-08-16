#!/usr/bin/env python3
"""Download open woody-plant datasets and write compact CSVs into data/external/."""

from __future__ import annotations

import csv
import io
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "external"
CACHE = Path("/tmp/open-plants")

USDA_TRAITS_URL = "https://raw.githubusercontent.com/emlys/trait-scripts/master/symbol_to_data.csv"
USDA_NAMES_URL = "https://raw.githubusercontent.com/emlys/trait-scripts/master/binomial_to_symbol.csv"
SF_URL = "https://data.sfgov.org/resource/vmnk-skih.csv?$limit=50000"
GLOBUNT_URL = "https://zenodo.org/records/7994433/files/GlobUNT_Species_2023.txt?download=1"
OPENPLANT_URL = "https://raw.githubusercontent.com/cwfrazier1/openplantdb/main/data/plants.csv"

WOODY_TOKENS = {"tree", "shrub", "subshrub"}
OPENPLANT_KEEP = (
    "tree",
    "shrub",
    "vine",
    "citrus",
    "nut",
    "fig",
    "blueberry",
    "bramble",
    "gooseberry",
    "grape",
    "muscadine",
    "holly",
)
OPENPLANT_DROP = ("strawberry", "ground fruit", "vegetable", "cover-crop")


def fetch(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "woody-plants-search/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        dest.write_bytes(response.read())
    return dest


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def preferred_scientific_name(names: list[str], genus: str) -> tuple[str, str]:
    unique: list[str] = []
    seen: set[str] = set()
    for name in names:
        cleaned = " ".join(name.split())
        if cleaned and cleaned.lower() not in seen:
            unique.append(cleaned)
            seen.add(cleaned.lower())
    if not unique:
        return "", ""
    genus_l = genus.lower().strip()

    def score(name: str) -> tuple[int, int, int]:
        parts = name.split()
        genus_match = 1 if genus_l and parts and parts[0].lower() == genus_l else 0
        is_binomial = 1 if len(parts) == 2 and "×" not in name else 0
        return (genus_match, is_binomial, -len(name))

    unique.sort(key=score, reverse=True)
    primary = unique[0]
    synonyms = "; ".join(n for n in unique[1:] if n != primary)
    return primary, synonyms


def is_woody(habit: str) -> bool:
    tokens = {part.strip().lower() for part in habit.replace(",", " ").split() if part.strip()}
    return bool(tokens & WOODY_TOKENS)


def build_usda() -> None:
    traits = fetch(USDA_TRAITS_URL, CACHE / "symbol_to_data.csv")
    names = fetch(USDA_NAMES_URL, CACHE / "binomial_to_symbol.csv")
    names_by_symbol: dict[str, list[str]] = defaultdict(list)
    with names.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("Accepted Symbol") or "").strip()
            name = (row.get("Scientific Name") or "").strip()
            if symbol and name:
                names_by_symbol[symbol].append(name)
    rows = []
    with traits.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            habit = (row.get("Growth Habit") or "").strip()
            if not is_woody(habit):
                continue
            symbol = (row.get("Accepted Symbol") or "").strip()
            genus = (row.get("Genus") or "").strip()
            scientific, synonyms = preferred_scientific_name(names_by_symbol.get(symbol, []), genus)
            if not scientific:
                scientific = genus
            if not scientific:
                continue
            rows.append(
                {
                    "scientific_name": scientific,
                    "synonyms": synonyms,
                    "common_name": (row.get("Common Name") or "").strip(),
                    "family": (row.get("Family") or "").strip(),
                    "genus": genus,
                    "growth_habit": habit,
                    "duration": (row.get("Duration") or "").strip(),
                    "native_status": (row.get("Native Status") or "").strip(),
                    "height_mature_ft": (row.get("Height, Mature (feet)") or "").strip(),
                    "leaf_retention": (row.get("Leaf Retention") or "").strip(),
                    "flower_color": (row.get("Flower Color") or "").strip(),
                    "bloom_period": (row.get("Bloom Period") or "").strip(),
                    "drought_tolerance": (row.get("Drought Tolerance") or "").strip(),
                    "shade_tolerance": (row.get("Shade Tolerance") or "").strip(),
                    "lifespan": (row.get("Lifespan") or "").strip(),
                    "usda_symbol": symbol,
                    "catalog_source": "USDA PLANTS (public domain)",
                }
            )
    write_csv(
        OUT_DIR / "usda_woody_plants.csv",
        [
            "scientific_name",
            "synonyms",
            "common_name",
            "family",
            "genus",
            "growth_habit",
            "duration",
            "native_status",
            "height_mature_ft",
            "leaf_retention",
            "flower_color",
            "bloom_period",
            "drought_tolerance",
            "shade_tolerance",
            "lifespan",
            "usda_symbol",
            "catalog_source",
        ],
        rows,
    )


def build_sf() -> None:
    path = fetch(SF_URL, CACHE / "sf_plants.csv")
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            plant_type = (row.get("plant_type") or "").lower()
            if not any(token in plant_type for token in ("tree", "shrub", "vine")):
                continue
            latin = (row.get("latin_name") or "").strip()
            if not latin:
                continue
            rows.append(
                {
                    "scientific_name": latin,
                    "common_name": (row.get("common_name") or "").strip(),
                    "family": (row.get("family_name") or "").strip(),
                    "growth_habit": (row.get("plant_type") or "").strip(),
                    "native_status": (row.get("climate_appropriate_plants") or "").strip(),
                    "flower_color": (row.get("flower_color") or "").strip(),
                    "bloom_period": (row.get("bloom_time") or "").strip(),
                    "notes": (row.get("additional_characteristices_notes") or "").strip(),
                    "habitat_value": (row.get("habitat_value") or "").strip(),
                    "associated_wildlife": (row.get("associated_wildlife") or "").strip(),
                    "water_needs": (row.get("water_needs") or "").strip(),
                    "soil_type": (row.get("soil_type") or "").strip(),
                    "plant_communities": (row.get("plant_communities") or "").strip(),
                    "catalog_source": "SF Plant Finder (DataSF, CC)",
                }
            )
    write_csv(
        OUT_DIR / "sf_plant_finder_woody.csv",
        [
            "scientific_name",
            "common_name",
            "family",
            "growth_habit",
            "native_status",
            "flower_color",
            "bloom_period",
            "notes",
            "habitat_value",
            "associated_wildlife",
            "water_needs",
            "soil_type",
            "plant_communities",
            "catalog_source",
        ],
        rows,
    )


def build_globunt() -> None:
    path = fetch(GLOBUNT_URL, CACHE / "globunt.txt")
    rows = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        seen: set[str] = set()
        for row in reader:
            name = (row.get("scientificFinal") or row.get("Species") or "").strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "scientific_name": name,
                    "family": (row.get("Family") or "").strip(),
                    "genus": (row.get("Genus") or "").strip(),
                    "growth_habit": "Tree",
                    "catalog_source": "GlobUNT / Kindt et al. 2023 (CC BY)",
                }
            )
    write_csv(
        OUT_DIR / "globunt_useful_trees.csv",
        ["scientific_name", "family", "genus", "growth_habit", "catalog_source"],
        rows,
    )


def build_openplantdb() -> None:
    path = fetch(OPENPLANT_URL, CACHE / "openplantdb.csv")
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            blob = f"{row.get('category') or ''} {row.get('subcategory') or ''}".lower()
            if any(drop in blob for drop in OPENPLANT_DROP):
                continue
            if not any(keep in blob for keep in OPENPLANT_KEEP):
                continue
            scientific = (row.get("scientific_name") or "").strip()
            if not scientific:
                continue
            height_in = (row.get("height_in_max") or row.get("height_in_min") or "").strip()
            height_ft = ""
            try:
                if height_in:
                    height_ft = str(round(float(height_in) / 12, 1))
            except ValueError:
                height_ft = ""
            zone_min = (row.get("usda_zone_min") or "").strip()
            zone_max = (row.get("usda_zone_max") or "").strip()
            zone = "-".join(part for part in (zone_min, zone_max) if part)
            rows.append(
                {
                    "scientific_name": scientific,
                    "common_name": (row.get("common_name") or "").strip(),
                    "category": (row.get("category") or "").strip(),
                    "growth_habit": (row.get("subcategory") or "").strip(),
                    "height_mature_ft": height_ft,
                    "shade_tolerance": (row.get("sun") or "").strip(),
                    "notes": (row.get("directions") or "").strip(),
                    "usda_hardiness_zone": zone,
                    "water": (row.get("water") or "").strip(),
                    "catalog_source": "OpenPlantDB (CC0)",
                }
            )
    write_csv(
        OUT_DIR / "openplantdb_woody.csv",
        [
            "scientific_name",
            "common_name",
            "category",
            "growth_habit",
            "height_mature_ft",
            "shade_tolerance",
            "notes",
            "usda_hardiness_zone",
            "water",
            "catalog_source",
        ],
        rows,
    )


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    build_usda()
    build_sf()
    build_globunt()
    build_openplantdb()


if __name__ == "__main__":
    main()
