#!/usr/bin/env python3
"""Build a woody-plant seed CSV from USDA PLANTS trait tables."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

WOODY_TOKENS = {"tree", "shrub", "subshrub"}
SOURCE_DIR = Path("/tmp/plants")
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "woody_plants.csv"

SEED_FIELDS = [
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


def is_woody(habit: str) -> bool:
    tokens = {part.strip().lower() for part in habit.replace(",", " ").split() if part.strip()}
    return bool(tokens & WOODY_TOKENS)


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


def main() -> None:
    names_by_symbol: dict[str, list[str]] = defaultdict(list)
    with (SOURCE_DIR / "binomial_to_symbol.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("Accepted Symbol") or "").strip()
            name = (row.get("Scientific Name") or "").strip()
            if symbol and name:
                names_by_symbol[symbol].append(name)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with (SOURCE_DIR / "symbol_to_data.csv").open(newline="", encoding="utf-8") as source, OUT_PATH.open(
        "w", newline="", encoding="utf-8"
    ) as dest:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(dest, fieldnames=SEED_FIELDS)
        writer.writeheader()
        for row in reader:
            habit = (row.get("Growth Habit") or "").strip()
            if not is_woody(habit):
                continue
            symbol = (row.get("Accepted Symbol") or "").strip()
            genus = (row.get("Genus") or "").strip()
            scientific, synonyms = preferred_scientific_name(names_by_symbol.get(symbol, []), genus)
            if not scientific:
                scientific = genus
            writer.writerow(
                {
                    "scientific_name": scientific,
                    "synonyms": synonyms,
                    "common_name": (row.get("Common Name") or "").strip(),
                    "family": (row.get("Family") or "").strip(),
                    "genus": genus,
                    "growth_habit": habit,
                    "duration": (row.get("Duration") or "").strip(),
                    "native_status": (row.get("Native Status") or "").strip(),
                    "category": (row.get("Category") or "").strip(),
                    "height_mature_ft": (row.get("Height, Mature (feet)") or "").strip(),
                    "leaf_retention": (row.get("Leaf Retention") or "").strip(),
                    "flower_color": (row.get("Flower Color") or "").strip(),
                    "bloom_period": (row.get("Bloom Period") or "").strip(),
                    "drought_tolerance": (row.get("Drought Tolerance") or "").strip(),
                    "shade_tolerance": (row.get("Shade Tolerance") or "").strip(),
                    "lifespan": (row.get("Lifespan") or "").strip(),
                    "usda_symbol": symbol,
                }
            )
            written += 1

    print(f"Wrote {written} woody plants to {OUT_PATH}")


if __name__ == "__main__":
    main()
