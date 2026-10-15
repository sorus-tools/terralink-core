"""Compare actual analytical outputs against the released QGIS reference."""

import json
from pathlib import Path

import pytest
import jsonschema
from pyogrio import raw
from shapely import from_wkb, from_wkt

from terralink_core import RunConfig, run_raster, run_vector
from terralink_core.models import STRATEGIES

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "conformance/fixtures"


@pytest.mark.parametrize("strategy", list(STRATEGIES))
@pytest.mark.parametrize("case", ["plain", "gap", "sealed", "raster"])
def test_released_qgis_geometry_topology_budget_and_metrics(tmp_path, strategy, case):
    reference = json.loads(
        (ROOT / f"conformance/expected/{case}_{strategy}.json").read_text()
    )
    config = RunConfig(
        budget_area=2,
        min_patch_size=0.01,
        min_corridor_width=20,
        max_search_distance=800,
        grid_resolution=10,
        strategy=strategy,
        analysis_crs="EPSG:32631",
        routing_enabled=case == "gap",
    )
    if case == "raster":
        config = RunConfig(
            budget_area=200,
            min_patch_size=1,
            min_corridor_width=2,
            max_search_distance=80,
            units="pixels",
            strategy=strategy,
            analysis_crs="EPSG:32631",
        )
        result = run_raster(FIXTURES / "habitat.tif", tmp_path / "run", config)
    else:
        obstacles = (
            None
            if case == "plain"
            else FIXTURES / f"barrier_{'gap' if case == 'gap' else 'sealed'}.geojson"
        )
        result = run_vector(
            FIXTURES / "patches.geojson", tmp_path / "run", config, obstacles=obstacles
        )
    for key, expected in reference["stats"].items():
        if isinstance(expected, (int, float)):
            assert result.stats[key] == pytest.approx(
                expected, abs=reference["numeric_absolute_tolerance"], rel=1e-9
            ), key
        else:
            assert result.stats[key] == expected, key
    meta, _, geometries, columns = raw.read(
        str(result.corridors_path), layer=result.corridor_layer
    )
    props = dict(zip(meta["fields"], columns))
    unmatched = [
        (str(props["patch_ids"][i]), from_wkb(geom))
        for i, geom in enumerate(geometries)
    ]
    for expected in reference["corridors"]:
        ref_geom = from_wkt(expected["wkt"])
        matches = [
            (i, geom.symmetric_difference(ref_geom).area)
            for i, (ids, geom) in enumerate(unmatched)
            if ids == expected["patch_ids"]
        ]
        assert matches, f"Missing corridor between {expected['patch_ids']}"
        index, difference = min(matches, key=lambda pair: pair[1])
        assert difference <= reference["geometry_tolerance_m2"], (
            f"Geometry differs by {difference} square metres"
        )
        unmatched.pop(index)
    assert not unmatched
    manifest = json.loads(result.manifest_path.read_text())
    jsonschema.validate(
        manifest,
        json.loads((ROOT / "spec/schemas/run-manifest.schema.json").read_text()),
    )
    assert manifest["implementation"] == "python"
    assert manifest["input_files"][0]["sha256"]
    assert manifest["schema_version"] == "1.0.0"
