"""Run the bundled vector landscape with the public standalone API."""

from pathlib import Path

from terralink_core import RunConfig, run_vector

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    config = RunConfig(
        budget_area=2,
        min_patch_size=0.01,
        min_corridor_width=20,
        max_search_distance=800,
        analysis_crs="EPSG:32631",
    )
    result = run_vector(
        root / "conformance/fixtures/patches.geojson",
        root / "run-output/python-example",
        config,
    )
    print(result.manifest_path)
