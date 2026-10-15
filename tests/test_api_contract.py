import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from terralink_core import RunConfig, TerraLinkError, run_vector
from terralink_core.io_backend import rasterize_geoms

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "conformance/fixtures"


def settings(**changes):
    defaults = {
        "budget_area": 2,
        "min_patch_size": 0.01,
        "min_corridor_width": 20,
        "max_search_distance": 800,
        "analysis_crs": "EPSG:32631",
    }
    defaults.update(changes)
    return RunConfig(**defaults)


@pytest.mark.parametrize(
    "field,value",
    [
        ("budget_area", True),
        ("min_patch_size", "oops"),
        ("patch_range", 1),
        ("patch_values", [True]),
        ("strategy", "typo"),
        ("max_search_distance", float("inf")),
    ],
)
def test_invalid_configuration_is_explicit(field, value):
    with pytest.raises(TerraLinkError):
        settings(**{field: value})


def test_fractional_pixel_quantities_are_not_silently_rounded():
    with pytest.raises(TerraLinkError, match="whole-cell"):
        settings(units="pixels", budget_area=1.9, min_patch_size=1)


def test_area_units_are_equivalent(tmp_path):
    metric = run_vector(FIXTURES / "patches.geojson", tmp_path / "metric", settings())
    imperial = run_vector(
        FIXTURES / "patches.geojson",
        tmp_path / "imperial",
        settings(
            units="imperial",
            budget_area=2 / 0.40468564224,
            min_patch_size=0.01 / 0.40468564224,
            min_corridor_width=20 / 0.3048,
            max_search_distance=800 / 0.3048,
            grid_resolution=10 / 0.3048,
        ),
    )
    assert imperial.stats["budget_used_ha"] == pytest.approx(
        metric.stats["budget_used_ha"], abs=1e-8
    )
    assert imperial.stats["corridors_used"] == metric.stats["corridors_used"]


def test_nullable_chain_ids_preserve_sql_null(tmp_path):
    result = run_vector(
        FIXTURES / "patches.geojson",
        tmp_path / "run",
        settings(strategy="landscape_fluidity"),
    )
    with sqlite3.connect(result.corridors_path) as db:
        assert all(
            row[0] is None for row in db.execute('SELECT chain_id FROM "Corridors"')
        )


def test_no_feasible_corridors_raise_a_clear_error(tmp_path):
    original = json.loads((FIXTURES / "patches.geojson").read_text())
    original["features"] = original["features"][:2]
    habitat = tmp_path / "two.geojson"
    habitat.write_text(json.dumps(original))
    with pytest.raises(TerraLinkError, match="no feasible corridors"):
        run_vector(
            habitat,
            tmp_path / "run",
            settings(),
            obstacles=FIXTURES / "barrier_sealed.geojson",
        )
    assert (tmp_path / "run/run.log").exists()
    assert not (tmp_path / "run/run.json").exists()


def test_metrics_rasterizer_honors_elongated_extent_cell_cap():
    mask, pixel = rasterize_geoms([], 1, None, max_cells=10, bounds=(0, 0, 100, 10))
    assert mask.size <= 10


def test_existing_run_is_not_overwritten(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    keep = output / "existing.txt"
    keep.write_text("keep")
    with pytest.raises(TerraLinkError, match="new or empty"):
        run_vector(FIXTURES / "patches.geojson", output, settings())
    assert keep.read_text() == "keep"


def test_standalone_import_does_not_load_qgis():
    code = 'from terralink_core._engine import analysis_vector; import sys; assert not any(n == "qgis" or n.startswith("qgis.") for n in sys.modules)'
    subprocess.run([sys.executable, "-c", code], check=True)


def test_cli_errors_are_json_with_nonzero_exit(tmp_path):
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps({"input": "missing.geojson", "parameters": settings().to_dict()})
    )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "terralink_core.cli",
            "run",
            "--config",
            str(request),
            "--output",
            str(tmp_path / "result"),
        ],
        text=True,
        capture_output=True,
    )
    assert process.returncode == 2
    assert "does not exist" in json.loads(process.stderr)["message"]
