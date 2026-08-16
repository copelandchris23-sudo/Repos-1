# Woody Plants Search

A local search engine for trees, shrubs, and other woody plants. It ships with a starter catalog derived from [USDA PLANTS](https://plants.usda.gov/) trait tables (public-domain U.S. government data), and you can replace that catalog by uploading your own CSV, TSV, or JSON file.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Upload a dataset

Use **Choose file** on the page, or:

```bash
curl -F "file=@your-plants.csv" http://127.0.0.1:8000/api/upload
```

These column names are mapped automatically when present:

- scientific name / latin name / binomial
- common name
- family, genus
- growth habit / plant type
- native status, duration, height, flower color, bloom period
- drought tolerance, shade tolerance, leaf retention, USDA symbol

Any other columns are kept as extra attributes and remain full-text searchable.

## Tests

```bash
pytest
```

## Starter catalog

`data/woody_plants.csv` is built by `scripts/build_seed.py` from USDA PLANTS symbol and synonym tables. It keeps taxa whose growth habit includes tree, shrub, or subshrub.
