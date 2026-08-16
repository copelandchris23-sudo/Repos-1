# Woody Plants Search

A local search engine for woody plants. The default index combines:

- The 2021 woody plant spreadsheet in this repo
- [USDA PLANTS](https://plants.usda.gov/) woody taxa (public-domain U.S. government data)
- [GlobalUsefulNativeTrees (GlobUNT)](https://doi.org/10.1038/s41598-023-39552-1) (CC BY)
- [SF Plant Finder](https://data.sfgov.org/Energy-and-Environment/San-Francisco-Plant-Finder-Data/vmnk-skih) woody species (DataSF)
- Woody/fruit-tree records from [OpenPlantDB](https://github.com/cwfrazier1/openplantdb) (CC0)

Names already in the 2021 catalog are kept; open datasets only add species that are not already present.

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
