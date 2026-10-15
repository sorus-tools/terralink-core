import io
import json
from pathlib import Path
import zipfile

import pytest

from terralink_core.web import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "conformance/fixtures"


@pytest.fixture
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "STORAGE_ROOT": str(tmp_path / "jobs"),
            "RUNS_PER_HOUR": 20,
            "PREVIEWS_PER_HOUR": 20,
        }
    )
    return app.test_client()


def test_health_capabilities_and_missing_input(client):
    assert client.get("/api/healthz").status_code == 200
    data = client.get("/api/capabilities").json
    assert len(data["strategies"]) == 4
    assert client.post("/api/run").status_code == 400


def test_vector_http_analysis_download_and_preview(client):
    params = {
        "layer_type": "vector",
        "budget_area": 2,
        "min_patch_size": 0.01,
        "min_corridor_width": 20,
        "max_search_distance": 800,
        "grid_resolution": 10,
        "analysis_crs": "EPSG:32631",
    }
    response = client.post(
        "/api/run",
        data={
            "params": json.dumps(params),
            "file": (
                io.BytesIO((FIXTURES / "patches.geojson").read_bytes()),
                "patches.geojson",
            ),
        },
    )
    assert response.status_code == 200, response.json
    data = response.json
    assert data["stats"]["corridors_used"] == 2
    assert {"input", "corridors", "contiguous"} <= set(data["previews"])
    manifest = next(item for item in data["outputs"] if item["filename"] == "run.json")
    download = client.get(manifest["url"])
    assert download.status_code == 200
    assert json.loads(download.data)["implementation"] == "python"
    assert "/Users/" not in download.get_data(as_text=True)
    assert client.get(data["previews"]["corridors"]["url"]).json["features"]


def test_raster_http_analysis(client):
    response = client.post(
        "/run",
        data={
            "params": json.dumps(
                {
                    "layer_type": "raster",
                    "raster_budget": 200,
                    "raster_min_patch_size": 1,
                    "raster_min_width": 2,
                    "raster_max_search": 80,
                    "raster_patch_values": "1",
                }
            ),
            "file": (
                io.BytesIO((FIXTURES / "habitat.tif").read_bytes()),
                "habitat.tif",
            ),
        },
    )
    assert response.status_code == 200, response.json
    assert any(item["filename"] == "corridors.tif" for item in response.json["outputs"])


def test_preview_and_reject_archive_escape(client, tmp_path):
    preview = client.post(
        "/preview",
        data={
            "file": (
                io.BytesIO((FIXTURES / "patches.geojson").read_bytes()),
                "patches.geojson",
            )
        },
    )
    assert preview.status_code == 200
    assert "input" in preview.json["previews"]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape.geojson", "{}")
    archive.seek(0)
    response = client.post("/preview", data={"file": (archive, "unsafe.zip")})
    assert response.status_code == 400
    assert "unsafe" in response.json["error"]


def test_foreign_origin_and_oversized_request(client):
    assert (
        client.post("/run", headers={"Origin": "https://untrusted.example"}).status_code
        == 403
    )
    client.application.config["MAX_CONTENT_LENGTH"] = 100
    response = client.post(
        "/run", data={"file": (io.BytesIO(b"x" * 500), "patches.geojson")}
    )
    assert response.status_code == 413
