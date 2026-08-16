from pathlib import Path

import pytest

from app.ingest import ingest_file, map_headers, parse_tabular

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


def test_map_headers_understands_2021_catalog_names():
    mapping = map_headers(["Botanic", "comm_ful", "Habit (tree, shrub, vine)", "Max Height (ft)"])
    assert mapping["Botanic"] == "scientific_name"
    assert mapping["comm_ful"] == "common_name"
    assert mapping["Habit (tree, shrub, vine)"] == "growth_habit"
    assert mapping["Max Height (ft)"] == "height_mature_ft"


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
