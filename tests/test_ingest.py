from pathlib import Path

import pytest

from app.ingest import enrich_empty_fields, ingest_file, lookup_from_csv, map_headers, parse_tabular

FIXTURE = Path(__file__).parent / "fixtures" / "sample_plants.csv"
OFFICIAL = Path(__file__).parent / "fixtures" / "official_format.csv"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "plants.db"


def test_map_headers_understands_common_aliases():
    mapping = map_headers(["Scientific Name", "Common Name", "Notes"])
    assert mapping["Scientific Name"] == "scientific_name"
    assert mapping["Common Name"] == "common_name"
    assert mapping["Notes"] == "extra:Notes"


def test_map_headers_understands_conservation_status():
    mapping = map_headers(["Botanic", "Conservation Status", "IUCN Red List"])
    assert mapping["Botanic"] == "scientific_name"
    assert mapping["Conservation Status"] == "conservation_status"
    assert mapping["IUCN Red List"] == "extra:IUCN Red List"


def test_map_headers_understands_hardiness_zone():
    mapping = map_headers(["Botanic", "USDA Hardiness Zone", "RHS Hardiness Rating"])
    assert mapping["USDA Hardiness Zone"] == "usda_hardiness_zone"
    assert mapping["RHS Hardiness Rating"] == "extra:RHS Hardiness Rating"


def test_map_headers_understands_2021_catalog_names():
    mapping = map_headers(["Botanic", "comm_ful", "Habit (tree, shrub, vine)", "Max Height (ft)"])
    assert mapping["Botanic"] == "scientific_name"
    assert mapping["comm_ful"] == "common_name"
    assert mapping["Habit (tree, shrub, vine)"] == "growth_habit"
    assert mapping["Max Height (ft)"] == "height_mature_ft"


def test_enrich_fills_empty_conservation_without_overwriting(db_path, tmp_path):
    ingest_file(FIXTURE, db_path=db_path)
    overlay = tmp_path / "iucn.csv"
    overlay.write_text(
        "scientific_name,conservation_status,growth_habit\n"
        "Quercus alba,Endangered,Tree\n"
        "Acer rubrum,Least Concern,Tree\n",
        encoding="utf-8",
    )
    first = enrich_empty_fields(lookup_from_csv(overlay), ["conservation_status"], db_path=db_path)
    assert first["updated"] == 2
    from app.search import search_plants

    oak = search_plants("oak", db_path=db_path)["results"][0]
    assert oak["conservation_status"] == "Endangered"
    threatened = search_plants("threatened", db_path=db_path)
    assert "white oak" in {row["common_name"] for row in threatened["results"]}

    overlay.write_text(
        "scientific_name,conservation_status\nQuercus alba,Least Concern\n",
        encoding="utf-8",
    )
    second = enrich_empty_fields(lookup_from_csv(overlay), ["conservation_status"], db_path=db_path)
    assert second["updated"] == 0
    oak = search_plants("oak", db_path=db_path)["results"][0]
    assert oak["conservation_status"] == "Endangered"


def test_ingest_keeps_named_and_extra_columns(db_path):
    result = ingest_file(FIXTURE, db_path=db_path)
    assert result["count"] == 3
    assert "scientific_name" in result["mapped_columns"]
    assert "Notes" in result["extra_columns"]


def test_parse_skips_leading_empty_row():
    headers, rows = parse_tabular("official.csv", OFFICIAL.read_bytes())
    assert "Botanic" in headers
    assert len(rows) == 3
    assert rows[0]["Botanic"] == "Tsuga canadensis"
