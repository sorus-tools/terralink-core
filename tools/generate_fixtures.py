"""Generate small, redistributable synthetic inputs; no external data required."""

import json
from pathlib import Path


def collection(rectangles):
    features = []
    for i, (x1, y1, x2, y2) in enumerate(rectangles, 1):
        ring = [
            [500000 + x1, 5000000 + y1],
            [500000 + x2, 5000000 + y1],
            [500000 + x2, 5000000 + y2],
            [500000 + x1, 5000000 + y2],
            [500000 + x1, 5000000 + y1],
        ]
        features.append(
            {
                "type": "Feature",
                "id": i,
                "properties": {"patch_id": i},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:32631"}},
        "features": features,
    }


def main():
    root = Path(__file__).resolve().parents[1] / "conformance/fixtures"
    root.mkdir(parents=True, exist_ok=True)
    cases = {
        "patches": [(0, 0, 100, 100), (300, 0, 400, 100), (300, 300, 400, 400)],
        "barrier_sealed": [(180, -5000, 220, 5000)],
        "barrier_gap": [(180, -5000, 220, 25), (180, 100, 220, 5000)],
    }
    for name, rectangles in cases.items():
        (root / f"{name}.geojson").write_text(
            json.dumps(collection(rectangles), indent=2) + "\n"
        )
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    values = np.zeros((60, 60), dtype="uint8")
    values[30:40, 5:15] = 1
    values[30:40, 35:45] = 1
    values[5:15, 35:45] = 1
    with rasterio.open(
        root / "habitat.tif",
        "w",
        driver="GTiff",
        height=60,
        width=60,
        count=1,
        dtype="uint8",
        crs="EPSG:32631",
        transform=from_origin(500000, 5000600, 10, 10),
        nodata=255,
    ) as ds:
        ds.write(values, 1)


if __name__ == "__main__":
    main()
