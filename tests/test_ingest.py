from pathlib import Path

import pytest

from app.ingest import ingest_file, map_headers

FIXTURE = Path(__file__).parent / "fixtures" / "sample_plants.csv"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "plants.db"


def test_map_headers_understands_common_aliases():
    mapping = map_headers(["Scientific Name", "Common Name", "Notes"])
    assert mapping["Scientific Name"] == "scientific_name"
    assert mapping["Common Name"] == "common_name"
    assert mapping["Notes"] == "extra:Notes"


def test_ingest_keeps_named_and_extra_columns(db_path):
    result = ingest_file(FIXTURE, db_path=db_path)
    assert result["count"] == 3
    assert "scientific_name" in result["mapped_columns"]
    assert "Notes" in result["extra_columns"]
