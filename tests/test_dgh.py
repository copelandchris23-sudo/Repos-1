from pathlib import Path

from app.ingest import enrich_empty_fields, ingest_file, lookup_from_csv
from app.search import get_plant, search_plants

SEED = Path(__file__).parent / "fixtures" / "sample_plants.csv"


def test_genus_overlay_fills_production_traits(tmp_path):
    db_path = tmp_path / "plants.db"
    ingest_file(SEED, db_path=db_path)
    overlay = tmp_path / "dgh.csv"
    overlay.write_text(
        "genus,thin_barked,coarse_roots,production_method,planting_season\n"
        "Acer,X,,Mostly container,spring\n"
        "Quercus,,X,In-ground,fall\n",
        encoding="utf-8",
    )
    result = enrich_empty_fields(
        lookup_from_csv(overlay, by="genus"),
        ["thin_barked", "coarse_roots", "production_method", "planting_season"],
        db_path=db_path,
        by="genus",
    )
    assert result["updated"] == 2
    maple = search_plants("Acer rubrum", db_path=db_path)["results"][0]
    oak = search_plants("Quercus alba", db_path=db_path)["results"][0]
    dogwood = search_plants("Cornus sericea", db_path=db_path)["results"][0]
    assert maple["thin_barked"] == "Yes"
    assert maple["production_method"] == "Mostly container"
    assert maple["planting_season"] == "Spring"
    assert oak["coarse_roots"] == "Yes"
    assert oak["production_method"] == "In-ground"
    assert oak["planting_season"] == "Fall"
    assert not dogwood["thin_barked"]
    plant = get_plant(maple["id"], db_path=db_path)
    assert "thin-barked" in plant["extra_text"].lower()


def test_thin_barked_and_planting_season_filters(tmp_path):
    db_path = tmp_path / "plants.db"
    ingest_file(SEED, db_path=db_path)
    overlay = tmp_path / "dgh.csv"
    overlay.write_text(
        "genus,thin_barked,planting_season\nAcer,Yes,Spring\n",
        encoding="utf-8",
    )
    enrich_empty_fields(
        lookup_from_csv(overlay, by="genus"),
        ["thin_barked", "planting_season"],
        db_path=db_path,
        by="genus",
    )
    thin = search_plants("", selected={"thin_barked": ["Yes"]}, db_path=db_path)
    spring = search_plants("", selected={"planting_season": ["Spring"]}, db_path=db_path)
    assert {row["common_name"] for row in thin["results"]} == {"red maple"}
    assert {row["common_name"] for row in spring["results"]} == {"red maple"}
