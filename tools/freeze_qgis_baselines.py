"""Reduce captured QGIS output to portable, reviewable conformance expectations."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    expected = root / "conformance/expected"
    keys = {
        "corridors_used",
        "budget_used_ha",
        "total_connected_area_ha",
        "largest_group_area_ha",
        "patches_total",
        "patches_connected",
        "components_remaining",
        "redundant_links",
        "avg_degree",
        "networkmerge_objective_post",
        "largestnetwork_objective_post",
    }
    count = 0
    for path in sorted(args.capture.glob("*/result.json")):
        result = json.loads(path.read_text())
        result["stats"] = {
            k: v
            for k, v in result["stats"].items()
            if k in keys or k.endswith(("_pre_exact", "_post_exact"))
        }
        result["source_revision"] = json.loads(
            (root / "source-provenance.json").read_text()
        )["revision"]
        result["geometry_tolerance_m2"] = 0.001
        result["numeric_absolute_tolerance"] = 1e-7
        (expected / f"{path.parent.name}.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        count += 1
    if count != 16:
        raise RuntimeError(f"Expected 16 successful baselines, found {count}")
    fixture_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "conformance/fixtures").iterdir())
        if p.is_file() and p.suffix.lower() in {'.tif','.geojson'}
    }
    (root / "conformance/fixture-hashes.json").write_text(
        json.dumps(fixture_hashes, indent=2) + "\n"
    )
    print(f"Frozen {count} QGIS reference cases")


if __name__ == "__main__":
    main()
