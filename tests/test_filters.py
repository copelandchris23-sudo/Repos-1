from pathlib import Path

from app.filters import is_conifer, selected_filters, zone_bounds
from app.ingest import ingest_file
from app.search import facets, search_plants

FIXTURE = Path(__file__).parent / "fixtures" / "filter_plants.csv"


def load(db_path):
    ingest_file(FIXTURE, db_path=db_path)
    return db_path


def names(payload):
    return {row["common_name"] for row in payload["results"]}


def test_selected_filters_accepts_repeated_values():
    chosen = selected_filters({"growth_habit": ["Tree", "Shrub"], "hardiness_zone": "4"})
    assert chosen["growth_habit"] == ["Tree", "Shrub"]
    assert chosen["hardiness_zone"] == ["4"]


def test_zone_bounds_and_conifer_helpers():
    assert zone_bounds("8b-11") == (8, 11)
    assert zone_bounds("3") == (3, 3)
    assert is_conifer("Pinaceae") == 1
    assert is_conifer("Fagaceae") == 0


def test_habit_checkboxes_are_combined(tmp_path):
    db_path = load(tmp_path / "plants.db")
    found = search_plants("", selected={"growth_habit": ["Shrub", "Vine"]}, db_path=db_path)
    assert names(found) == {"red-osier dogwood", "Chinese wisteria"}


def test_filters_across_groups_narrow_the_list(tmp_path):
    db_path = load(tmp_path / "plants.db")
    found = search_plants(
        "",
        selected={"growth_habit": ["Tree"], "leaf_retention": ["Evergreen"]},
        db_path=db_path,
    )
    assert names(found) == {"eastern white pine", "eastern hemlock"}


def test_hardiness_zone_matches_ranges(tmp_path):
    db_path = load(tmp_path / "plants.db")
    zone4 = search_plants("", selected={"hardiness_zone": ["4"]}, db_path=db_path)
    zone2 = search_plants("", selected={"hardiness_zone": ["2"]}, db_path=db_path)
    assert "white oak" in names(zone4)
    assert "red maple" in names(zone4)
    assert "red-osier dogwood" not in names(zone4)
    assert names(zone2) == {"red-osier dogwood"}


def test_broadleaf_and_conifer_filters(tmp_path):
    db_path = load(tmp_path / "plants.db")
    conifer = search_plants("", selected={"foliage_type": ["conifer"]}, db_path=db_path)
    broadleaf = search_plants("", selected={"foliage_type": ["broadleaf"]}, db_path=db_path)
    assert names(conifer) == {"eastern white pine", "eastern hemlock"}
    assert "white oak" in names(broadleaf)
    assert "eastern white pine" not in names(broadleaf)


def test_flower_color_and_height_buckets(tmp_path):
    db_path = load(tmp_path / "plants.db")
    purple = search_plants("", selected={"flower_color": ["purple"]}, db_path=db_path)
    tall = search_plants("", selected={"height": ["80-plus"]}, db_path=db_path)
    assert names(purple) == {"Chinese wisteria"}
    assert names(tall) == {"white oak", "eastern white pine", "eastern hemlock"}


def test_facets_include_checkbox_counts(tmp_path):
    db_path = load(tmp_path / "plants.db")
    data = facets(selected={"growth_habit": ["Tree"]}, db_path=db_path)
    habits = {
        item["value"]: item["count"]
        for item in next(group["options"] for group in data["groups"] if group["key"] == "growth_habit")
    }
    zones = {
        item["value"]: item["count"]
        for item in next(group["options"] for group in data["groups"] if group["key"] == "hardiness_zone")
    }
    assert data["total"] == 4
    assert habits["Tree"] == 4
    assert habits["Shrub"] == 1
    assert zones["4"] == 2
    assert any(group["key"] == "family" and group["options"] for group in data["groups"])
