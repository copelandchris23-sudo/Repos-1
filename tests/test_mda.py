from pathlib import Path

from app.ingest import enrich_empty_fields, ingest_file, lookup_from_csv, map_headers
from app.mda import aggregate_mda_rows, parse_mda_html
from app.search import get_plant, search_plants

FIXTURE = Path(__file__).parent / "fixtures" / "mda_hardiness.html"


def test_map_headers_understands_minimum_hardiness_zone():
    mapping = map_headers(["Scientific Name", "Minimum Hardiness Zone"])
    assert mapping["Scientific Name"] == "scientific_name"
    assert mapping["Minimum Hardiness Zone"] == "usda_hardiness_zone"


def test_parse_and_aggregate_keeps_woody_plants_only():
    records = aggregate_mda_rows(parse_mda_html(FIXTURE.read_text(encoding="utf-8")))
    by_name = {row["scientific_name"]: row for row in records}

    assert "Echinacea purpurea" not in by_name
    assert "Panicum virgatum" not in by_name
    assert "Fragaria × ananassa" not in by_name
    assert "Fragaria x ananassa" not in by_name
    assert "Malus Hybrid" not in by_name

    maple = by_name["Acer palmatum"]
    assert maple["usda_hardiness_zone"] == "4-5"
    assert maple["growth_habit"] == "Tree"

    hybrid = by_name["Acer × freemanii"]
    assert hybrid["usda_hardiness_zone"] == "4"

    pine = by_name["Pinus strobus"]
    assert pine["leaf_retention"] == "Evergreen"
    assert pine["growth_habit"] == "Tree"
    assert pine["usda_hardiness_zone"] == "3"

    assert by_name["Cornus sericea"]["growth_habit"] == "Shrub"
    assert by_name["Rosa rugosa"]["growth_habit"] == "Shrub"
    assert by_name["Celastrus scandens"]["growth_habit"] == "Vine"
    assert by_name["Malus domestica"]["growth_habit"] == "Tree"
    assert by_name["Vaccinium corymbosum"]["growth_habit"] == "Shrub"
    assert by_name["Vitis riparia"]["growth_habit"] == "Vine"


def test_mda_overlay_fills_empty_hardiness_zone(tmp_path):
    db_path = tmp_path / "plants.db"
    seed = tmp_path / "seed.csv"
    seed.write_text(
        "scientific_name,common_name,growth_habit\nAcer palmatum,Japanese maple,Tree\n",
        encoding="utf-8",
    )
    ingest_file(seed, db_path=db_path)
    overlay = tmp_path / "mda.csv"
    overlay.write_text(
        "scientific_name,usda_hardiness_zone,mda_hardiness_zone,catalog_source\n"
        "Acer palmatum,4-5,4-5,Minnesota Department of Agriculture Cold Hardiness List\n",
        encoding="utf-8",
    )
    result = enrich_empty_fields(
        lookup_from_csv(overlay),
        ["usda_hardiness_zone"],
        db_path=db_path,
    )
    assert result["updated"] == 1
    found = search_plants("zone 4-5", db_path=db_path)
    assert found["results"][0]["scientific_name"].startswith("Acer palmatum")
    plant = get_plant(found["results"][0]["id"], db_path=db_path)
    assert plant["usda_hardiness_zone"] == "4-5"
    assert plant["extra"]["mda_hardiness_zone"] == "4-5"
