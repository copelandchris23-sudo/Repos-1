# Woody Plants Search

A local search engine for woody plants. The default index combines:

- The 2021 woody plant spreadsheet in this repo
- [Arnold Arboretum](https://arboretum.harvard.edu/) living-collection taxa and growth habit (public Arboretum Explorer layer)
- [Trees and Shrubs Online](https://www.treesandshrubsonline.org/) (International Dendrology Society) — USDA/RHS hardiness, cultivated dimensions, native range/provenance, and taxonomic notes
- [USDA PLANTS](https://plants.usda.gov/) woody taxa (public-domain U.S. government data)
- [GlobalUsefulNativeTrees (GlobUNT)](https://doi.org/10.1038/s41598-023-39552-1) (CC BY)
- [SF Plant Finder](https://data.sfgov.org/Energy-and-Environment/San-Francisco-Plant-Finder-Data/vmnk-skih) woody species (DataSF)
- Woody/fruit-tree records from [OpenPlantDB](https://github.com/cwfrazier1/openplantdb) (CC0)

Conservation status is attached afterwards from the [IUCN Red List](https://www.iucnredlist.org/) Darwin Core archive hosted by [GBIF](https://doi.org/10.15468/0qnb58) (CC BY). Tree habit for that overlay uses [BGCI GlobalTreeSearch](https://tools.bgci.org/global_tree_search.php) as a checklist only; the GlobalTreeSearch download itself is CC BY-NC-ND and is not redistributed. BGCI leads the Global Tree Assessment that feeds IUCN tree assessments.

Names already in the 2021 catalog are kept; later datasets only add species that are not already present. Arnold habit, IUCN/BGCI conservation status, and Trees and Shrubs Online hardiness, height, and provenance fill empty fields on existing rows.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Refresh open datasets

```bash
python3 scripts/build_external_catalogs.py
```

That writes compact CSVs into `data/external/`. Restart the app or use **Restore combined catalog**.

## Upload another dataset

Use **Choose file** on the page, or:

```bash
curl -F "file=@your-plants.csv" http://127.0.0.1:8000/api/upload
```

## Tests

```bash
pytest
```
