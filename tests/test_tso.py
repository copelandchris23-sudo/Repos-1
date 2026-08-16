from pathlib import Path

from app.tso import extract_tso_height_ft, parse_tso_article, tso_species_urls

FIXTURE = Path(__file__).parent / "fixtures" / "tso_article.html"


def test_tso_species_urls_skip_genera_and_cultivars():
    sitemap = """
    <urlset>
      <loc>https://www.treesandshrubsonline.org/articles/eucryphia/</loc>
      <loc>https://www.treesandshrubsonline.org/articles/eucryphia/eucryphia-x-hillieri/</loc>
      <loc>https://www.treesandshrubsonline.org/articles/abelia/abelia-chinensis/abelia-chinensis-keiser/</loc>
      <loc>https://www.treesandshrubsonline.org/articles/abelia/abelia-edward-goucher-cultivars/</loc>
    </urlset>
    """
    urls = tso_species_urls(sitemap)
    assert urls == ["https://www.treesandshrubsonline.org/articles/eucryphia/eucryphia-x-hillieri/"]


def test_parse_tso_article_extracts_hardiness_height_and_provenance():
    record = parse_tso_article(
        FIXTURE.read_text(encoding="utf-8"),
        "https://www.treesandshrubsonline.org/articles/eucryphia/eucryphia-x-hillieri/",
    )
    assert record is not None
    assert record["scientific_name"].startswith("Eucryphia")
    assert "hillieri" in record["scientific_name"]
    assert record["family"] == "Cunoniaceae"
    assert record["usda_hardiness_zone"] == "8b-11"
    assert record["rhs_hardiness_rating"] == "H5"
    assert record["height_mature_ft"] == "32.8"
    assert "hybrid" in record["native_status"].lower()
    assert record["tso_url"].endswith("eucryphia-x-hillieri/")


def test_scientific_from_url():
    from app.tso import scientific_from_url

    assert scientific_from_url("https://www.treesandshrubsonline.org/articles/aesculus/aesculus-wilsonii/") == "Aesculus wilsonii"
    assert (
        scientific_from_url("https://www.treesandshrubsonline.org/articles/eucryphia/eucryphia-x-hillieri/")
        == "Eucryphia × hillieri"
    )


def test_extract_tso_height_prefers_typical_meters():
    assert extract_tso_height_ft("An evergreen tree to 10 m tall. A specimen reached 14 m.") == "32.8"
    assert extract_tso_height_ft("reaching in places 100 to 150 ft") == "150"
