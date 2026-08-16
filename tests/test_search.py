from pathlib import Path

from app.ingest import ingest_file
from app.search import search_plants

FIXTURE = Path(__file__).parent / "fixtures" / "sample_plants.csv"


def load(db_path):
    ingest_file(FIXTURE, db_path=db_path)
    return db_path


def names(payload):
    return {row["common_name"] for row in payload["results"]}


def test_search_by_common_name(tmp_path):
    db_path = load(tmp_path / "plants.db")
    found = search_plants("oak", db_path=db_path)
    assert found["total"] == 1
    assert names(found) == {"white oak"}


def test_search_by_scientific_name(tmp_path):
    db_path = load(tmp_path / "plants.db")
    found = search_plants("Acer rubrum", db_path=db_path)
    assert names(found) == {"red maple"}


def test_search_extra_column_and_derived_trait(tmp_path):
    db_path = load(tmp_path / "plants.db")
    riparian = search_plants("riparian", db_path=db_path)
    drought = search_plants("drought tolerant", db_path=db_path)
    assert names(riparian) == {"red-osier dogwood"}
    assert names(drought) == {"white oak"}


def test_habit_filter(tmp_path):
    db_path = load(tmp_path / "plants.db")
    found = search_plants("", growth_habit="Shrub", db_path=db_path)
    assert names(found) == {"red-osier dogwood"}
