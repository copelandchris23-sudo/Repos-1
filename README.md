# Woody Plants Search

A local search engine for the 2021 woody plant catalog. Search by common name, scientific name, family, hardiness, wildlife notes, and other traits. You can replace the index by uploading another CSV, TSV, or JSON file.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Catalog

The default index is `data/Woody_Plant_Search_2021.csv`. Column names from that spreadsheet (`Botanic`, `comm_ful`, habit codes such as `T`/`S`, and the rest) are mapped automatically. Extra columns stay attached to each plant and remain full-text searchable.

## Upload another dataset

Use **Choose file** on the page, or:

```bash
curl -F "file=@your-plants.csv" http://127.0.0.1:8000/api/upload
```

## Tests

```bash
pytest
```
