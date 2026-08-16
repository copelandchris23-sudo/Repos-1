from pathlib import Path

from app.ingest import ingest_file
from app.search import get_plant, search_plants

FIXTURE = Path(__file__).parent / "fixtures" / "sample_plants.csv"
OFFICIAL = Path(__file__).parent / "fixtures" / "official_format.csv"


def load(db_path, fixture=FIXTURE):
    ingest_file(fixture, db_path=db_path)
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


def test_official_catalog_names_and_codes(tmp_path):
    db_path = load(tmp_path / "official.db", OFFICIAL)
    tsuga = search_plants("Tsuga", db_path=db_path)
    paperbark = search_plants("paperbark maple", db_path=db_path)
    shade = search_plants("shade tolerant", db_path=db_path)
    trees = search_plants("", growth_habit="Tree", db_path=db_path)
    assert tsuga["results"][0]["scientific_name"] == "Tsuga canadensis"
    assert names(paperbark) == {"paperbark maple"}
    assert {row["scientific_name"] for row in shade["results"]} == {"Tsuga canadensis"}
    assert trees["total"] == 3
    plant = get_plant(tsuga["results"][0]["id"], db_path=db_path)
    assert plant["growth_habit"] == "Tree"
    assert plant["leaf_retention"] == "Evergreen"
