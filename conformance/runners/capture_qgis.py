"""Capture the released QGIS algorithm with a headless QGIS Python runtime.

Usage: QGIS_PYTHON capture_qgis.py --plugin-parent PATH --output PATH
The source checkout must contain a TerraLink package; no running GUI is needed.
"""

import argparse
import contextlib
import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-parent", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case", choices=["plain", "gap", "sealed", "raster"])
    parser.add_argument("--strategy")
    args = parser.parse_args()
    sys.path.insert(0, args.plugin_parent)
    from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer

    app = QgsApplication([], False)
    app.initQgis()
    from TerraLink.analysis_vector import run_vector_analysis
    from TerraLink.analysis_raster import run_raster_analysis

    metadata = configparser.ConfigParser()
    metadata.read(Path(args.plugin_parent) / "TerraLink/metadata.txt")
    plugin_version = metadata.get("general", "version")
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    args.output.mkdir(parents=True, exist_ok=True)
    cases = [args.case] if args.case else ["plain", "gap", "sealed", "raster"]
    strategies = (
        [args.strategy]
        if args.strategy
        else [
            "most_connected_networks",
            "most_connected_networks_2",
            "largest_single_network",
            "landscape_fluidity",
        ]
    )
    for case in cases:
        for strategy in strategies:
            out = args.output / f"{case}_{strategy}"
            out.mkdir(exist_ok=True)
            log = io.StringIO()
            try:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    params = {
                        "min_patch_size": 0.01,
                        "budget_area": 2.0,
                        "min_corridor_width": 20.0,
                        "max_search_distance": 800.0,
                        "grid_resolution": 10.0,
                        "unit_system": "metric",
                        "analysis_crs_authid": "EPSG:32631",
                        "output_name": "corridors.gpkg",
                        "add_to_project": False,
                        "vector_routing_enabled": case == "gap",
                    }
                    if case == "raster":
                        layer = QgsRasterLayer(str(fixtures / "habitat.tif"), "habitat")
                        params.update(
                            {
                                "patch_values": [1],
                                "min_patch_size": 1,
                                "budget_pixels": 200,
                                "max_search_distance": 80,
                                "min_corridor_width": 2,
                                "patch_connectivity": 4,
                                "raster_units": "pixels",
                            }
                        )
                        result = run_raster_analysis(
                            layer, str(out), params, strategy=strategy
                        )[0]
                    else:
                        layer = QgsVectorLayer(
                            str(fixtures / "patches.geojson"), "patches", "ogr"
                        )
                        if case != "plain":
                            barriers = QgsVectorLayer(
                                str(
                                    fixtures
                                    / f"barrier_{'gap' if case == 'gap' else 'sealed'}.geojson"
                                ),
                                "barriers",
                                "ogr",
                            )
                            QgsProject.instance().addMapLayer(barriers, False)
                            params.update(
                                {
                                    "obstacle_enabled": True,
                                    "obstacle_layer_ids": [barriers.id()],
                                }
                            )
                        result = run_vector_analysis(
                            layer, str(out), params, strategy=strategy
                        )[0]
                        if case != "plain":
                            QgsProject.instance().removeMapLayer(barriers.id())
                corridor_layer = QgsVectorLayer(
                    f"{result['output_path']}|layername={result['layer_name']}",
                    "result",
                    "ogr",
                )
                rows = []
                for feature in corridor_layer.getFeatures():
                    rows.append(
                        {
                            "patch_ids": str(feature["patch_ids"]),
                            "corridor_area_ha": float(feature["corridor_area_ha"]),
                            "wkt": feature.geometry().asWkt(12),
                        }
                    )
                summary = {
                    "implementation": "qgis",
                    "plugin_version": plugin_version,
                    "case": case,
                    "strategy": strategy,
                    "stats": result["stats"],
                    "corridors": rows,
                }
                (out / "result.json").write_text(
                    json.dumps(summary, indent=2, default=str) + "\n"
                )
                print(
                    f"{case}/{strategy}: {len(rows)} corridors; budget={result['stats'].get('budget_used_ha')}"
                )
            except Exception as exc:
                traceback.print_exc(file=log)
                (out / "error.json").write_text(
                    json.dumps({"error": str(exc)}, indent=2) + "\n"
                )
                print(f"{case}/{strategy}: FAILED {exc}", file=sys.stderr)
            finally:
                (out / "run.log").write_text(log.getvalue())
    # QGIS object lifetime on interpreter shutdown is runtime-specific; outputs are flushed above.


if __name__ == "__main__":
    main()
