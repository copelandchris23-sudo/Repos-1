#!/usr/bin/env python3
"""Download open woody-plant datasets and write compact CSVs into data/external/."""

from __future__ import annotations

import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "external"
CACHE = Path("/tmp/open-plants")

USDA_TRAITS_URL = "https://raw.githubusercontent.com/emlys/trait-scripts/master/symbol_to_data.csv"
USDA_NAMES_URL = "https://raw.githubusercontent.com/emlys/trait-scripts/master/binomial_to_symbol.csv"
SF_URL = "https://data.sfgov.org/resource/vmnk-skih.csv?$limit=50000"
GLOBUNT_URL = "https://zenodo.org/records/7994433/files/GlobUNT_Species_2023.txt?download=1"
OPENPLANT_URL = "https://raw.githubusercontent.com/cwfrazier1/openplantdb/main/data/plants.csv"
ARNOLD_LAYER_URL = (
    "https://services1.arcgis.com/qN3V93cYGMKQCOxL/arcgis/rest/services/"
    "ARBEXPLORER_PLANTS/FeatureServer/0"
)
GTS_URL = "https://tools.bgci.org/GlobalTreeSearch%20download%201_10.csv"
IUCN_ZIP_URL = "https://hosted-datasets.gbif.org/datasets/iucn/iucn-latest.zip"

ARNOLD_FIELDS = (
    "SCIENTIFIC_NAME,COMMON_NAME,HABIT,FAMILY,GENUS,SYNONYMS_FULL,"
    "HEIGHT_NUM,HEIGHT_UNIT,IS_DEAD,NAME_STATUS,CULTIVAR,SPECIES"
)

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
    with urllib.request.urlopen(req, timeout=120) as response:
        dest.write_bytes(response.read())
    return dest


def fetch_json(url: str, retries: int = 4) -> dict:
    delay = 2
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "woody-plants-search/1.0"})
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


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


def first_common_name(value: str) -> str:
    if not value:
        return ""
    return re.split(r"[,;/]", value)[0].strip()


def height_to_feet(value: object, unit: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    unit_l = (unit or "").strip().lower()
    if unit_l.startswith("m"):
        number *= 3.28084
    if number <= 0:
        return ""
    return str(round(number, 1))


def build_arnold() -> None:
    taxa: dict[str, dict] = {}
    offset = 0
    page_size = 2000
    while True:
        query = urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": ARNOLD_FIELDS,
                "returnGeometry": "false",
                "resultRecordCount": page_size,
                "resultOffset": offset,
                "f": "json",
            }
        )
        payload = fetch_json(f"{ARNOLD_LAYER_URL}/query?{query}")
        features = payload.get("features") or []
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        for feature in features:
            attrs = feature.get("attributes") or {}
            scientific = " ".join((attrs.get("SCIENTIFIC_NAME") or "").split())
            if not scientific:
                continue
            key = scientific.lower()
            living = attrs.get("IS_DEAD") != 1
            record = taxa.get(key)
            if record is None:
                record = {
                    "scientific_name": scientific,
                    "common_name": first_common_name(attrs.get("COMMON_NAME") or ""),
                    "synonyms": " ".join((attrs.get("SYNONYMS_FULL") or "").split()),
                    "family": (attrs.get("FAMILY") or "").strip(),
                    "genus": (attrs.get("GENUS") or "").strip(),
                    "growth_habit": (attrs.get("HABIT") or "").strip(),
                    "height_mature_ft": height_to_feet(
                        attrs.get("HEIGHT_NUM"), attrs.get("HEIGHT_UNIT") or ""
                    ),
                    "living": 0,
                    "habit_counts": Counter(),
                    "common_counts": Counter(),
                    "catalog_source": "Arnold Arboretum living collection (Arboretum Explorer)",
                }
                taxa[key] = record
            if living:
                record["living"] += 1
            habit = (attrs.get("HABIT") or "").strip()
            if habit and (living or record["living"] == 0):
                record["habit_counts"][habit] += 1
            common = first_common_name(attrs.get("COMMON_NAME") or "")
            if common and (living or record["living"] == 0):
                record["common_counts"][common] += 1
            height = height_to_feet(attrs.get("HEIGHT_NUM"), attrs.get("HEIGHT_UNIT") or "")
            if living and height:
                try:
                    current = float(record["height_mature_ft"] or 0)
                    if float(height) > current:
                        record["height_mature_ft"] = height
                except ValueError:
                    record["height_mature_ft"] = height
            if living and not record["family"]:
                record["family"] = (attrs.get("FAMILY") or "").strip()
            if living and not record["genus"]:
                record["genus"] = (attrs.get("GENUS") or "").strip()
        if not features or len(features) < page_size:
            break
        offset += page_size
        if offset > 200000:
            break

    rows = []
    for record in taxa.values():
        if record["habit_counts"]:
            record["growth_habit"] = record["habit_counts"].most_common(1)[0][0]
        if record["common_counts"]:
            record["common_name"] = record["common_counts"].most_common(1)[0][0]
        rows.append(
            {
                "scientific_name": record["scientific_name"],
                "common_name": record["common_name"],
                "synonyms": record["synonyms"],
                "family": record["family"],
                "genus": record["genus"],
                "growth_habit": record["growth_habit"],
                "height_mature_ft": record["height_mature_ft"],
                "catalog_source": record["catalog_source"],
            }
        )
    rows.sort(key=lambda item: item["scientific_name"].lower())
    write_csv(
        OUT_DIR / "arnold_arboretum_inventory.csv",
        [
            "scientific_name",
            "common_name",
            "synonyms",
            "family",
            "genus",
            "growth_habit",
            "height_mature_ft",
            "catalog_source",
        ],
        rows,
    )


def binomial_key(name: str) -> str:
    parts = [part for part in re.split(r"\s+", (name or "").replace("×", " ").strip().lower()) if part]
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return parts[0] if parts else ""


def catalog_binomials() -> set[str]:
    names: set[str] = set()
    seed = ROOT / "data" / "Woody_Plant_Search_2021.csv"
    paths = [seed, *sorted(OUT_DIR.glob("*.csv"))]
    for path in paths:
        if not path.exists() or path.name == "iucn_conservation_status.csv":
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            name_field = next(
                (
                    field
                    for field in ("scientific_name", "Botanic", "botanic", "latin_name")
                    if field in fields
                ),
                None,
            )
            if not name_field:
                continue
            for row in reader:
                key = binomial_key(row.get(name_field) or "")
                if key:
                    names.add(key)
    return names


def gts_binomials(path: Path) -> set[str]:
    names: set[str] = set()
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        name_field = "TaxonName" if "TaxonName" in (reader.fieldnames or []) else (reader.fieldnames or [""])[0]
        for row in reader:
            taxon = (row.get(name_field) or "").strip()
            parts = taxon.split()
            if len(parts) >= 2:
                names.add(f"{parts[0]} {parts[1]}".lower())
    return names


def normalize_iucn_status(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    cleaned = re.sub(r"^lower risk[/: ]+", "", cleaned, flags=re.I)
    aliases = {
        "ex": "Extinct",
        "extinct": "Extinct",
        "ew": "Extinct in the Wild",
        "extinct in the wild": "Extinct in the Wild",
        "cr": "Critically Endangered",
        "critically endangered": "Critically Endangered",
        "en": "Endangered",
        "endangered": "Endangered",
        "vu": "Vulnerable",
        "vulnerable": "Vulnerable",
        "nt": "Near Threatened",
        "near threatened": "Near Threatened",
        "lc": "Least Concern",
        "least concern": "Least Concern",
        "dd": "Data Deficient",
        "data deficient": "Data Deficient",
        "cd": "Conservation Dependent",
        "conservation dependent": "Conservation Dependent",
        "lr/cd": "Conservation Dependent",
    }
    return aliases.get(cleaned.lower(), cleaned)


STATUS_RANK = {
    "Extinct": 0,
    "Extinct in the Wild": 1,
    "Critically Endangered": 2,
    "Endangered": 3,
    "Vulnerable": 4,
    "Near Threatened": 5,
    "Data Deficient": 6,
    "Least Concern": 7,
}


def build_iucn() -> None:
    gts_path = fetch(GTS_URL, CACHE / "gts.csv")
    trees = gts_binomials(gts_path)
    zip_path = fetch(IUCN_ZIP_URL, CACHE / "iucn-latest.zip")
    statuses: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open("distribution.txt") as handle:
            for raw in handle:
                parts = raw.decode("utf-8", "replace").rstrip("\n").split("\t")
                if len(parts) < 6:
                    continue
                taxon_id, _country, locality, _source, _means, threat = parts[:6]
                if locality.strip().lower() != "global" or not threat.strip():
                    continue
                status = normalize_iucn_status(threat)
                previous = statuses.get(taxon_id)
                if previous is None or STATUS_RANK.get(status, 99) < STATUS_RANK.get(previous, 99):
                    statuses[taxon_id] = status

        rows = []
        with archive.open("taxon.txt") as handle:
            for raw in handle:
                parts = raw.decode("utf-8", "replace").rstrip("\n").split("\t")
                if len(parts) < 13:
                    continue
                taxon_id, _scientific, kingdom, _phylum, _class, _order, family, genus, epithet = parts[:9]
                rank = parts[10] if len(parts) > 10 else ""
                infra = parts[11] if len(parts) > 11 else ""
                taxonomic_status = parts[12] if len(parts) > 12 else ""
                if kingdom.strip().upper() != "PLANTAE":
                    continue
                if taxonomic_status.strip().lower() not in {"accepted", ""}:
                    continue
                status = statuses.get(taxon_id)
                if not status:
                    continue
                genus = genus.strip()
                epithet = epithet.strip()
                if not genus or not epithet:
                    continue
                scientific = f"{genus} {epithet}"
                if rank.strip().lower() in {"subspecies", "variety", "form"} and infra.strip():
                    scientific = f"{genus} {epithet} {infra.strip()}"
                binomial = f"{genus} {epithet}".lower()
                rows.append(
                    {
                        "scientific_name": scientific,
                        "family": family.strip().title() if family else "",
                        "genus": genus,
                        "growth_habit": "Tree" if binomial in trees else "",
                        "conservation_status": status,
                        "catalog_source": (
                            "IUCN Red List via GBIF; tree habit from BGCI GlobalTreeSearch"
                        ),
                    }
                )
    wanted = catalog_binomials()
    # Prefer species-level rows when duplicates share a binomial; keep first severe status.
    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        key = " ".join(row["scientific_name"].lower().split()[:2])
        if wanted and key not in wanted:
            continue
        current = deduped.get(key)
        if current is None:
            deduped[key] = row
            continue
        if STATUS_RANK.get(row["conservation_status"], 99) < STATUS_RANK.get(
            current["conservation_status"], 99
        ):
            # keep more complete name if current is species-only
            row["growth_habit"] = row["growth_habit"] or current["growth_habit"]
            deduped[key] = row
        elif not current["growth_habit"] and row["growth_habit"]:
            current["growth_habit"] = row["growth_habit"]
    out_rows = sorted(deduped.values(), key=lambda item: item["scientific_name"].lower())
    write_csv(
        OUT_DIR / "iucn_conservation_status.csv",
        [
            "scientific_name",
            "family",
            "genus",
            "growth_habit",
            "conservation_status",
            "catalog_source",
        ],
        out_rows,
    )


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    build_usda()
    build_sf()
    build_globunt()
    build_openplantdb()
    build_arnold()
    build_iucn()


if __name__ == "__main__":
    main()
