"""Publish a measured, portable report without copying private source/log paths."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from shapely import from_wkt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--r-source", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    reports = root / "conformance/reports"
    reports.mkdir(exist_ok=True)
    cases = []
    for expected_path in sorted((root / "conformance/expected").glob("*.json")):
        current_path = args.capture / expected_path.name
        if not current_path.exists():
            raise RuntimeError(f"Missing capture {expected_path.name}")
        current = json.loads(current_path.read_text())
        expected = json.loads(expected_path.read_text())
        if "error" in current:
            cases.append(
                {"case": expected_path.stem, "agrees": False, "error": current["error"]}
            )
            continue
        geometries = current.get("geometry", [])
        if isinstance(geometries, str):
            geometries = [geometries]
        properties = current.get("corridors", [])
        if isinstance(properties, dict):
            properties = [properties]
        pixel_area = 0.01 if current["case"] == "raster" else 1.0
        budget = current["summary"]["budget_used"] * pixel_area
        reference_budget = expected["stats"]["budget_used_ha"]
        unmatched = [
            (str(row["patch_ids"]), from_wkt(geom))
            for row, geom in zip(properties, geometries)
        ]
        differences = []
        same_count = len(unmatched) == len(expected["corridors"])
        membership_agrees = sorted(row[0] for row in unmatched) == sorted(
            row["patch_ids"] for row in expected["corridors"]
        )
        for reference in expected["corridors"]:
            ref = from_wkt(reference["wkt"])
            choices = [
                (index, geom.symmetric_difference(ref).area)
                for index, (ids, geom) in enumerate(unmatched)
                if ids == reference["patch_ids"]
            ]
            if not choices:
                differences.append(None)
                continue
            index, difference = min(choices, key=lambda pair: pair[1])
            unmatched.pop(index)
            differences.append(difference)
        geometry_agrees = (
            same_count
            and not unmatched
            and all(
                v is not None and v <= expected["geometry_tolerance_m2"]
                for v in differences
            )
        )
        budget_agrees = (
            abs(budget - reference_budget) <= expected["numeric_absolute_tolerance"]
        )
        cases.append(
            {
                "case": expected_path.stem,
                "r_corridors": len(geometries),
                "qgis_corridors": len(expected["corridors"]),
                "r_budget_ha": budget,
                "qgis_budget_ha": reference_budget,
                "budget_difference_ha": budget - reference_budget,
                "matched_geometry_symmetric_difference_m2": differences,
                "geometry_agrees": geometry_agrees,
                "budget_agrees": budget_agrees,
                "membership_budget_agrees": membership_agrees and budget_agrees,
                "agrees": geometry_agrees and budget_agrees,
            }
        )
    source = {}
    if args.r_source:
        source["parent_revision"] = subprocess.check_output(
            ["git", "-C", str(args.r_source), "rev-parse", "HEAD"], text=True
        ).strip()
        source["working_tree_modified"] = bool(
            subprocess.check_output(
                ["git", "-C", str(args.r_source), "status", "--porcelain"], text=True
            ).strip()
        )
        h = hashlib.sha256()
        for path in sorted((args.r_source / "R").glob("*.R")):
            h.update(path.name.encode())
            h.update(path.read_bytes())
        source["r_sources_sha256"] = h.hexdigest()
    report = {
        "implementation": "r-native",
        "status": "measured differences; not universal parity",
        "source": source,
        "raster_connectivity": 4,
        "reference_plugin_version": "1.8.3",
        "comparison_scope": "Selected corridor membership, geometry, and normalized area budget on the bundled fixtures; not every R metric or arbitrary input.",
        "agreed_cases": sum(item["agrees"] for item in cases),
        "membership_budget_agreed_cases": sum(
            item.get("membership_budget_agrees", False) for item in cases
        ),
        "total_cases": len(cases),
        "cases": cases,
    }
    (reports / "r-native.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Native R compatibility capture",
        "",
        f"{report['agreed_cases']} of {len(cases)} cases agree on selected corridor geometry and normalized budget.",
        f"{report['membership_budget_agreed_cases']} of {len(cases)} agree on selected patch memberships and normalized budget; this weaker agreement does not establish identical corridor placement.",
        "",
        "This capture uses the identified working R source, not a claim about every public R release. Native R remains independent of Python/QGIS.",
        "",
        "| Case | R corridors | QGIS corridors | Budget difference (ha) | Geometry/budget agreement |",
        "|---|---:|---:|---:|---|",
    ]
    for item in cases:
        lines.append(
            f"| {item['case']} | {item.get('r_corridors', 'error')} | {item.get('qgis_corridors', '—')} | {item.get('budget_difference_ha', 0):.8g} | {'Pass' if item['agrees'] else 'Difference'} |"
        )
    lines.extend(
        [
            "",
            "Matching cases are regression evidence for these settings only. Gap routing and raster LSN/LF differences require further native R alignment before claiming a shared numerical profile.",
            "Even equal-budget vector cases can choose a different boundary location between equally distant patches. Strict polygon comparisons retain that difference rather than widening tolerances or treating similar scores as spatial equivalence.",
            "",
            "See `r-native.json` for source fingerprint, exact measurements, and comparison scope.",
        ]
    )
    (reports / "r-native.md").write_text("\n".join(lines) + "\n")
    print(f"R compatibility: {report['agreed_cases']}/{len(cases)} cases agree")


if __name__ == "__main__":
    main()
