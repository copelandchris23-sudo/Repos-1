import importlib

from fastapi.testclient import TestClient

from app.ingest import ingest_file


def test_upload_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANTS_DB_PATH", str(tmp_path / "api.db"))
    import app.db as db

    importlib.reload(db)
    import app.ingest as ingest

    importlib.reload(ingest)
    import app.search as search

    importlib.reload(search)
    import app.main as main

    importlib.reload(main)

    fixture = tmp_path / "empty.csv"
    fixture.write_text("scientific_name,common_name\n", encoding="utf-8")
    ingest_file(fixture, db_path=db.DB_PATH, replace=True)

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/upload",
            files={
                "file": (
                    "woody.csv",
                    "scientific_name,common_name,family\nQuercus alba,white oak,Fagaceae\n",
                    "text/csv",
                )
            },
        )
        assert upload.status_code == 200
        assert upload.json()["count"] == 1
        results = client.get("/api/search", params={"q": "oak"})
        assert results.status_code == 200
        payload = results.json()
        assert payload["total"] == 1
        assert payload["results"][0]["common_name"] == "white oak"
