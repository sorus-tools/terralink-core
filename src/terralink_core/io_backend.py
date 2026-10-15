"""File/raster operations for the preserved engine, using GDAL through public wheels.

Only presentation/I/O hooks are replaced. Candidate generation, objective scoring,
selection, final barrier admission, network construction, and metrics remain in
the extracted 1.8.3 engine.
"""

import math
from pathlib import Path

import numpy as np
from pyogrio import raw
from pyproj import Transformer
import rasterio.features
from rasterio.transform import from_origin
from shapely import to_wkb
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import transform as shapely_transform


def write_features(
    path,
    layer,
    records,
    source_crs,
    destination_crs=None,
    *,
    overwrite_file=False,
    field_schema=None,
):
    path = Path(path)
    if overwrite_file and path.exists():
        path.unlink()
    destination_crs = destination_crs or source_crs
    transformer = Transformer.from_crs(source_crs, destination_crs, always_xy=True)
    properties = [item[1] for item in records]
    fields = (
        list(properties[0])
        if properties
        else list(field_schema or {"corridor_id": "int64"})
    )
    geometries = []
    for geometry, _ in records:
        geom = geometry.constGet() if hasattr(geometry, "constGet") else geometry
        geom = shapely_transform(transformer.transform, geom)
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        if not isinstance(geom, MultiPolygon):
            polygon_parts = [
                part for part in getattr(geom, "geoms", []) if isinstance(part, Polygon)
            ]
            if not polygon_parts:
                raise ValueError(f"Output {layer} contains non-polygon geometry")
            geom = MultiPolygon(polygon_parts)
        geometries.append(to_wkb(geom))
    arrays = []
    masks = []
    for field in fields:
        values = [item.get(field) for item in properties]
        declared = (field_schema or {}).get(field)
        if declared == "str":
            array = np.array(
                ["" if v is None else str(v) for v in values], dtype=object
            )
        elif declared == "float64":
            array = np.array(
                [np.nan if v is None else v for v in values], dtype="float64"
            )
        elif not values or all(
            v is None or isinstance(v, (int, np.integer)) for v in values
        ):
            array = np.array([0 if v is None else v for v in values], dtype="int64")
        elif all(v is None or isinstance(v, (int, float, np.number)) for v in values):
            array = np.array(
                [np.nan if v is None else v for v in values], dtype="float64"
            )
        else:
            array = np.array(
                ["" if v is None else str(v) for v in values], dtype=object
            )
        arrays.append(array)
        masks.append(np.array([v is None for v in values], dtype=bool))
    raw.write(
        str(path),
        np.array(geometries, dtype=object),
        arrays,
        fields,
        field_mask=masks,
        layer=layer,
        driver="GPKG",
        geometry_type="MultiPolygon",
        crs=str(destination_crs),
    )


def write_corridors(
    corridors,
    patches,
    output_path,
    layer_name,
    target_crs,
    original_crs,
    unit_system,
    overwrite_file=False,
):
    from ._engine.analysis_vector import _source_patch_ids_for_internal_patch_ids

    imperial = unit_system == "imperial"
    suffix = "ac" if imperial else "ha"
    factor = 2.471053814 if imperial else 1.0
    rows = []
    for cid, cdata in corridors.items():
        ids = sorted(cdata["patch_ids"])
        touched = sorted(
            cdata.get("touched_patch_ids", cdata.get("raw_patch_ids", ids))
        )
        props = {
            "corridor_id": cid,
            "patch_ids": ",".join(map(str, ids)),
            "source_patch_ids": ",".join(
                map(str, _source_patch_ids_for_internal_patch_ids(ids, patches))
            ),
            "touched_patch_ids": ",".join(map(str, touched)),
            "source_touched_patch_ids": ",".join(
                map(str, _source_patch_ids_for_internal_patch_ids(touched, patches))
            ),
            f"corridor_area_{suffix}": round(
                float(cdata.get("corridor_area_ha", cdata.get("area_ha", 0))) * factor,
                4,
            ),
            f"patches_area_{suffix}": round(
                float(cdata.get("patches_area_ha", 0)) * factor, 4
            ),
            f"network_area_{suffix}": round(
                float(cdata.get("network_area_ha", cdata.get("connected_area_ha", 0)))
                * factor,
                4,
            ),
            "efficiency": round(float(cdata.get("efficiency", 0)), 6),
            "multipatch": str(cdata.get("multipatch_label", "")),
            "redundant": str(cdata.get("redundant_label", "")),
            "chain": str(cdata.get("chain_label", "No")),
            "chain_id": cdata.get("chain_id"),
            "chain_role": str(cdata.get("chain_role", "")),
            "chain_endpts": str(cdata.get("chain_endpoints", "")),
            "chain_path": str(cdata.get("chain_path", "")),
        }
        rows.append((cdata["geom"], props))
    schema = {
        "corridor_id": "int64",
        "patch_ids": "str",
        "source_patch_ids": "str",
        "touched_patch_ids": "str",
        "source_touched_patch_ids": "str",
        f"corridor_area_{suffix}": "float64",
        f"patches_area_{suffix}": "float64",
        f"network_area_{suffix}": "float64",
        "efficiency": "float64",
        "multipatch": "str",
        "redundant": "str",
        "chain": "str",
        "chain_id": "int64",
        "chain_role": "str",
        "chain_endpts": "str",
        "chain_path": "str",
    }
    write_features(
        output_path,
        layer_name,
        rows,
        target_crs.toWkt(),
        original_crs.toWkt(),
        overwrite_file=overwrite_file,
        field_schema=schema,
    )
    return True


def write_networks(
    networks, patches, output_path, layer_name, target_crs, original_crs, unit_system
):
    imperial = unit_system == "imperial"
    suffix = "ac" if imperial else "ha"
    factor = 2.471053814 if imperial else 1.0
    rows = []
    for net in networks:
        props = {
            "network_id": net["network_id"],
            "patch_ids": ",".join(map(str, sorted(net["patch_ids"]))),
            "patch_count": net["patch_count"],
            "corr_count": net["corridor_count"],
            f"area_{suffix}": net["area_ha"] * factor,
            f"patch_area_{suffix}": net["patch_area_ha"] * factor,
            f"corr_area_{suffix}": net["corridor_area_ha"] * factor,
            f"mean_patch_{suffix}": net["mean_patch_area_ha"] * factor,
            ("perimeter_ft" if imperial else "perimeter_m"): net["perimeter_m"]
            * (3.280839895 if imperial else 1.0),
            "corridor_pct": net["corridor_share_pct"],
        }
        rows.append((net["geom"], props))
    schema = {
        "network_id": "int64",
        "patch_ids": "str",
        "patch_count": "int64",
        "corr_count": "int64",
        f"area_{suffix}": "float64",
        f"patch_area_{suffix}": "float64",
        f"corr_area_{suffix}": "float64",
        f"mean_patch_{suffix}": "float64",
        ("perimeter_ft" if imperial else "perimeter_m"): "float64",
        "corridor_pct": "float64",
    }
    write_features(
        output_path,
        layer_name,
        rows,
        target_crs.toWkt(),
        original_crs.toWkt(),
        field_schema=schema,
    )
    return True


def rasterize_geoms(geoms, pixel_size_m, target_crs, max_cells=10_000_000, bounds=None):
    pixel = max(float(pixel_size_m or 0), 1.0)
    geoms = [geom for geom in geoms if geom is not None and not geom.isEmpty()]
    if bounds is None:
        if not geoms:
            return np.zeros((1, 1), dtype="uint8"), pixel
        bounds = (
            min(g.boundingBox().xMinimum() for g in geoms),
            min(g.boundingBox().yMinimum() for g in geoms),
            max(g.boundingBox().xMaximum() for g in geoms),
            max(g.boundingBox().yMaximum() for g in geoms),
        )
    xmin, ymin, xmax, ymax = bounds
    pad = pixel * 2
    xmin -= pad
    ymin -= pad
    xmax += pad
    ymax += pad
    width = max(xmax - xmin, pixel)
    height = max(ymax - ymin, pixel)
    cols = max(1, math.ceil(width / pixel))
    rows = max(1, math.ceil(height / pixel))
    if max_cells < 1:
        raise ValueError("max_cells must be positive")
    while rows * cols > max_cells:
        pixel *= max(1, math.ceil(math.sqrt(rows * cols / max_cells)))
        cols = max(1, math.ceil(width / pixel))
        rows = max(1, math.ceil(height / pixel))
    mask = (
        rasterio.features.rasterize(
            [(g.constGet(), 1) for g in geoms],
            out_shape=(rows, cols),
            transform=from_origin(xmin, ymax, pixel, pixel),
            fill=0,
            dtype="uint8",
        )
        if geoms
        else np.zeros((rows, cols), dtype="uint8")
    )
    return mask, pixel


def navigator_mask(self, geoms):
    geoms = [g for g in geoms if g is not None and not g.isEmpty()]
    if not geoms:
        return None
    return rasterio.features.rasterize(
        [(g.constGet(), 1) for g in geoms],
        out_shape=(self.rows, self.cols),
        transform=from_origin(
            self.origin_x, self.origin_y, self.resolution, self.resolution
        ),
        fill=0,
        dtype="uint8",
        all_touched=True,
    ).astype(bool)


def burn_geometries(self, geoms):
    mask = navigator_mask(self, geoms)
    if mask is None:
        return False
    self.passable[mask] = False
    return True


def install(engine):
    """Replace interface-specific operations once, with stateless implementations."""
    engine.write_corridors_layer_to_gpkg = write_corridors
    engine.write_contiguous_networks_layer_to_gpkg = write_networks
    engine.add_layer_to_qgis_from_gpkg = lambda *args, **kwargs: None
    engine._rasterize_geoms_to_mask = rasterize_geoms
    engine.RasterNavigator._burn_geometries_fast = burn_geometries
    engine.RasterNavigator._rasterize_geometries_mask = navigator_mask
