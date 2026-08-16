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


def test_conservation_status_filter(tmp_path):
    db_path = tmp_path / "status.db"
    ingest_file(FIXTURE, db_path=db_path)
    overlay = tmp_path / "status.csv"
    overlay.write_text(
        "scientific_name,conservation_status\n"
        "Quercus alba,Vulnerable\n"
        "Cornus sericea,Least Concern\n",
        encoding="utf-8",
    )
    from app.ingest import enrich_empty_fields, lookup_from_csv

    enrich_empty_fields(lookup_from_csv(overlay), ["conservation_status"], db_path=db_path)
    threatened = search_plants("", conservation_status="threatened", db_path=db_path)
    concern = search_plants("", conservation_status="Least Concern", db_path=db_path)
    assert names(threatened) == {"white oak"}
    assert names(concern) == {"red-osier dogwood"}


def test_habit_filter(tmp_path):
    db_path = load(tmp_path / "plants.db")
    found = search_plants("", growth_habit="Shrub", db_path=db_path)
    assert names(found) == {"red-osier dogwood"}


def test_hardiness_zone_is_searchable(tmp_path):
    db_path = tmp_path / "zone.db"
    extra = tmp_path / "tso_like.csv"
    extra.write_text(
        "scientific_name,common_name,usda_hardiness_zone,rhs_hardiness_rating\n"
        "Eucryphia hillieri,Hillier's eucryphia,8b-11,H5\n",
        encoding="utf-8",
    )
    ingest_file(extra, db_path=db_path)
    found = search_plants("zone 8b-11", db_path=db_path)
    assert names(found) == {"Hillier's eucryphia"}
    plant = get_plant(found["results"][0]["id"], db_path=db_path)
    assert plant["usda_hardiness_zone"] == "8b-11"


def test_skip_existing_binomials_when_merging(tmp_path):
    db_path = tmp_path / "merge.db"
    ingest_file(FIXTURE, db_path=db_path, replace=True)
    extra = tmp_path / "usda_like.csv"
    extra.write_text(
        "scientific_name,common_name,family,catalog_source\n"
        "Quercus alba,white oak,Fagaceae,USDA PLANTS\n"
        "Tsuga canadensis,eastern hemlock,Pinaceae,USDA PLANTS\n",
        encoding="utf-8",
    )
    result = ingest_file(extra, db_path=db_path, replace=False, skip_existing=True)
    assert result["count"] == 1
    assert result["skipped"] == 1
    hemlock = search_plants("hemlock", db_path=db_path)
    assert names(hemlock) == {"eastern hemlock"}


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
