"""File-based standalone workflows around the preserved active TerraLink engine."""

from contextlib import redirect_stdout
from dataclasses import fields
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import random
from threading import RLock

import numpy as np
from pyogrio import raw
from pyproj import CRS
from pyproj.exceptions import CRSError
import rasterio
from rasterio.features import rasterize, shapes
from shapely import from_wkb, get_num_coordinates
from shapely.geometry import shape

from . import ALGORITHM_PROFILE, UPSTREAM_REVISION, __version__
from .models import RunConfig, RunResult, TerraLinkError

_RUN_LOCK = RLock()


def _digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _portable_paths(value, output):
    if isinstance(value, dict):
        return {key: _portable_paths(item, output) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable_paths(item, output) for item in value]
    if isinstance(value, (str, Path)):
        try:
            return Path(value).relative_to(output).as_posix()
        except (ValueError, OSError):
            pass
    return value


def _load_layer(path, layer=None):
    from .geometry.compat import (
        QgsVectorLayer,
        QgsGeometry,
        QgsFeature,
        QgsFields,
        QgsField,
    )

    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise TerraLinkError(f"Input file does not exist: {path.name}")
    try:
        meta, fids, geometries, arrays = raw.read(
            str(path), layer=layer, return_fids=True
        )
    except (RuntimeError, OSError) as exc:
        raise TerraLinkError(f"Cannot read vector input {path.name}: {exc}") from exc
    if not meta.get("crs"):
        raise TerraLinkError("Input has no coordinate reference system")
    features = []
    names = list(meta["fields"])
    field_defs = QgsFields([QgsField(str(name)) for name in names])
    for i, geometry in enumerate(geometries):
        if geometry is None:
            raise TerraLinkError(f"Feature {i} has null geometry")
        geom = from_wkb(geometry)
        if geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise TerraLinkError(
                f"Feature {i} must be Polygon or MultiPolygon, found {geom.geom_type}"
            )
        feature = QgsFeature()
        feature.setId(int(fids[i]))
        feature.setGeometry(QgsGeometry(geom))
        feature.setAttributes(
            [
                array[i].item() if isinstance(array[i], np.generic) else array[i]
                for array in arrays
            ]
        )
        features.append(feature)
    return QgsVectorLayer.from_features(
        features, crs=meta["crs"], fields=field_defs, name=path.stem
    )


def _check_analysis_crs(layer, config):
    source = CRS.from_user_input(layer.crs().toWkt())
    if config.analysis_crs:
        try:
            analysis = CRS.from_user_input(config.analysis_crs)
        except CRSError as exc:
            raise TerraLinkError(
                "analysis_crs is not a valid coordinate reference system"
            ) from exc
        if not analysis.is_projected or any(
            abs(axis.unit_conversion_factor - 1) > 1e-9
            for axis in analysis.axis_info[:2]
        ):
            raise TerraLinkError("analysis_crs must be projected with metre axes")
        return analysis.to_string()
    if source.is_geographic:
        extent = layer.extent()
        if extent.width() > 6 or extent.yMinimum() < -80 or extent.yMaximum() > 84:
            raise TerraLinkError(
                "This geographic extent needs an explicit suitable projected analysis_crs"
            )
    return None


def _params(config, layer):
    from ._engine.analysis_vector import VectorRunParams

    known = {field.name for field in fields(VectorRunParams)}
    protected = {
        "budget_area",
        "min_patch_size",
        "min_corridor_width",
        "max_search_distance",
        "unit_system",
        "output_name",
        "obstacle_enabled",
        "obstacle_layer_ids",
        "grid_resolution",
    }
    invalid = set(config.engine_options) - known
    if invalid or set(config.engine_options) & protected:
        raise TerraLinkError(
            f"Unsupported or reserved engine_options: {sorted(invalid | (set(config.engine_options) & protected))}"
        )
    if config.units == "pixels":
        raise TerraLinkError("pixels units are only supported for raster inputs")
    distance_factor = 0.3048 if config.units == "imperial" else 1.0
    area_factor = 0.40468564224 if config.units == "imperial" else 1.0
    params = {
        **config.engine_options,
        "min_patch_size": config.min_patch_size * area_factor,
        "budget_area": config.budget_area * area_factor,
        "min_corridor_width": config.min_corridor_width * distance_factor,
        "max_search_distance": config.max_search_distance * distance_factor,
        "grid_resolution": config.grid_resolution * distance_factor,
        "unit_system": config.units,
        "vector_routing_enabled": config.routing_enabled,
        "output_name": "corridors.gpkg",
        "add_to_project": False,
    }
    crs = _check_analysis_crs(layer, config)
    if not crs:
        from ._engine.analysis_vector import get_utm_crs_from_extent

        crs = get_utm_crs_from_extent(layer).authid()
    params["analysis_crs_authid"] = crs
    return params


def _execute(
    layer,
    output_dir,
    config,
    params,
    inputs,
    *,
    obstacle_layers=(),
    progress=None,
    raster_source=None,
):
    from ._engine import analysis_vector as engine
    from .geometry.compat import QgsProject
    from .io_backend import install

    output = Path(output_dir).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise TerraLinkError(
            "Output directory must be new or empty to avoid overwriting an existing run"
        )
    output.mkdir(parents=True, exist_ok=True)
    log = io.StringIO()
    with _RUN_LOCK:
        random_state = random.getstate()
        numpy_state = np.random.get_state()
        random.seed(config.seed)
        np.random.seed(config.seed % 2**32)
        registered = []
        try:
            install(engine)
            for obstacle in obstacle_layers:
                QgsProject.instance().addMapLayer(obstacle, False)
                registered.append(obstacle.id())
            if registered:
                params.update(obstacle_enabled=True, obstacle_layer_ids=registered)
            with redirect_stdout(log):
                result = engine.run_vector_analysis(
                    layer,
                    str(output),
                    params,
                    strategy=config.strategy,
                    temporary=False,
                    progress_cb=progress,
                )[0]
            stats = result["stats"]
            gpkg = Path(result["output_path"])
            # The legacy UI code tolerated export/report failures. A library must report them.
            if not gpkg.is_file():
                raise TerraLinkError(
                    "Engine did not produce its corridor output; see run.log"
                )
            meta, _, geometries, _ = raw.read(str(gpkg), layer=result["layer_name"])
            if len(geometries) != int(stats.get("corridors_used", 0)):
                raise TerraLinkError(
                    "Output feature count differs from selected corridor count"
                )
            raw.read(str(gpkg), layer="Contiguous Areas")
            report = Path(stats.get("landscape_metrics_path", ""))
            if not report.is_file() or report.read_text(encoding="utf-8").startswith(
                "Landscape analysis failed:"
            ):
                raise TerraLinkError("Landscape metrics failed; see run.log")
            if (
                float(stats.get("budget_used_ha", 0))
                > float(params["budget_area"]) + 1e-7
            ):
                raise TerraLinkError(
                    "Selected corridors exceed the configured area budget"
                )
            _verify_barriers(gpkg, result["layer_name"], obstacle_layers, params)
            if raster_source:
                _verify_raster_barriers(gpkg, result["layer_name"], raster_source)
            raster_paths = (
                _write_display_rasters(
                    gpkg, result["layer_name"], output, raster_source
                )
                if raster_source
                else []
            )
            inputs = [
                {"name": Path(path).name, "sha256": _digest(path)} for path in inputs
            ]
            normalized = {
                key: value
                for key, value in params.items()
                if not key.startswith("_") and key not in {"obstacle_layer_ids"}
            }
            manifest = {
                "schema_version": "1.0.0",
                "implementation": "python",
                "implementation_version": __version__,
                "algorithm_profile": ALGORITHM_PROFILE,
                "upstream_revision": UPSTREAM_REVISION,
                "engine_source_sha256": _digest(Path(engine.__file__)),
                "input_mode": "raster" if raster_source else "vector",
                "strategy": config.strategy,
                "configuration": config.to_dict(),
                "normalized_parameters": normalized,
                "input_files": inputs,
                "source_crs": layer.crs().toWkt(),
                "stats": stats,
                "reproducibility": {
                    "seed": config.seed,
                    "wall_clock_limited_search": True,
                    "notice": "A fixed seed does not make wall-clock-limited searches identical across machines.",
                },
                "dependencies": {
                    name: importlib.metadata.version(name)
                    for name in ["numpy", "shapely", "pyproj", "rasterio", "pyogrio"]
                },
                "warnings": [
                    line.strip() for line in log.getvalue().splitlines() if "⚠" in line
                ],
                "outputs": {
                    "geopackage": gpkg.name,
                    "corridor_layer": result["layer_name"],
                    "network_layer": "Contiguous Areas",
                    "metrics_report": report.name,
                    "rasters": raster_paths,
                },
            }
            clean = json.dumps(
                _json_safe(_portable_paths(manifest, output)), indent=2, allow_nan=False
            )
            manifest_path = output / "run.json"
            manifest_path.write_text(clean + "\n", encoding="utf-8")
            (output / "metrics.json").write_text(
                json.dumps(
                    _json_safe(_portable_paths(stats, output)),
                    indent=2,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            return RunResult(
                output,
                gpkg,
                result["layer_name"],
                "Contiguous Areas",
                _json_safe(stats),
                manifest_path,
                report,
            )
        except Exception as exc:
            if isinstance(exc, TerraLinkError):
                raise
            raise TerraLinkError(str(exc)) from exc
        finally:
            for lid in registered:
                QgsProject.instance().removeMapLayer(lid)
            random.setstate(random_state)
            np.random.set_state(numpy_state)
            (output / "run.log").write_text(log.getvalue(), encoding="utf-8")


def _verify_barriers(gpkg, layer, obstacles, params):
    if not obstacles:
        return
    from pyproj import Transformer
    from shapely.ops import transform
    from shapely import union_all

    meta, _, wkb, _ = raw.read(str(gpkg), layer=layer)
    analysis = params.get("analysis_crs_authid") or meta["crs"]
    convert = Transformer.from_crs(meta["crs"], analysis, always_xy=True)
    corridor_geoms = [transform(convert.transform, from_wkb(g)) for g in wkb]
    for obstacle in obstacles:
        convert_obs = Transformer.from_crs(
            obstacle.crs().toWkt(), analysis, always_xy=True
        )
        union = union_all(
            [
                transform(convert_obs.transform, f.geometry().constGet())
                for f in obstacle.getFeatures()
            ]
        )
        if any(g.intersection(union).area > 1e-7 for g in corridor_geoms):
            raise TerraLinkError("Final corridor output overlaps an impassable polygon")


def run_vector(
    input_path, output_dir, config, *, obstacles=None, layer=None, progress=None
):
    if not isinstance(config, RunConfig):
        raise TerraLinkError("config must be a RunConfig")
    habitat = _load_layer(input_path, layer)
    params = _params(config, habitat)
    obstacles = (
        []
        if obstacles is None
        else ([obstacles] if isinstance(obstacles, (str, Path)) else list(obstacles))
    )
    obstacle_layers = [_load_layer(path) for path in obstacles]
    return _execute(
        habitat,
        output_dir,
        config,
        params,
        [input_path, *obstacles],
        obstacle_layers=obstacle_layers,
        progress=progress,
    )


def run_raster(input_path, output_dir, config, *, progress=None):
    from dataclasses import replace
    from .geometry.compat import QgsVectorLayer, QgsGeometry

    if not isinstance(config, RunConfig):
        raise TerraLinkError("config must be a RunConfig")
    input_path = Path(input_path).expanduser().resolve()
    if not input_path.is_file():
        raise TerraLinkError(f"Input file does not exist: {input_path.name}")
    with rasterio.open(input_path) as ds:
        if ds.crs is None:
            raise TerraLinkError("Raster has no CRS")
        crs = CRS.from_user_input(ds.crs)
        if not crs.is_projected:
            raise TerraLinkError(
                "Raster inputs require a projected CRS; reproject before running"
            )
        if (
            ds.transform.b
            or ds.transform.d
            or ds.transform.a <= 0
            or ds.transform.e >= 0
        ):
            raise TerraLinkError(
                "Raster must use a north-up grid with positive cell width"
            )
        if config.band > ds.count:
            raise TerraLinkError("Requested raster band does not exist")
        if ds.width * ds.height > 40_000_000:
            raise TerraLinkError("Raster exceeds the 40 million cell processing limit")
        data = ds.read(config.band, masked=True)
        valid = ~np.ma.getmaskarray(data) & np.isfinite(np.asarray(data))
        values = np.asarray(data, dtype=np.float64)
        habitat = np.zeros(data.shape, dtype=bool)
        for value in config.patch_values:
            habitat |= np.abs(values - value) < config.value_tolerance
        if config.patch_range is not None:
            habitat |= (values >= config.patch_range[0]) & (
                values <= config.patch_range[1]
            )
        habitat &= valid
        if not habitat.any():
            raise TerraLinkError(
                "Selected habitat values produced no valid habitat pixels"
            )
        obstacles = np.zeros(data.shape, dtype=bool)
        for value in config.obstacle_values:
            obstacles |= np.abs(values - value) < config.value_tolerance
        if config.obstacle_range is not None:
            obstacles |= (values >= config.obstacle_range[0]) & (
                values <= config.obstacle_range[1]
            )
        obstacles &= valid & ~habitat
        geometries = []
        vertices = 0
        for geom, value in shapes(
            habitat.astype("uint8"),
            mask=habitat,
            transform=ds.transform,
            connectivity=config.patch_connectivity,
        ):
            if value != 1:
                continue
            geometry = shape(geom)
            vertices += get_num_coordinates(geometry)
            if vertices > 150000:
                raise TerraLinkError(
                    "Polygonized raster exceeds 150,000 vertices; aggregate or crop the input"
                )
            geometries.append(QgsGeometry(geometry))
        layer = QgsVectorLayer.from_geometries(
            geometries, crs=crs.to_string(), name=input_path.stem
        )
        unit_factor = crs.axis_info[0].unit_conversion_factor
        pixel_width = abs(ds.transform.a) * unit_factor
        pixel_height = abs(ds.transform.e) * unit_factor
        if config.units == "pixels":
            normalized = replace(
                config,
                units="metric",
                budget_area=int(config.budget_area)
                * pixel_width
                * pixel_height
                / 10000,
                min_patch_size=int(config.min_patch_size)
                * pixel_width
                * pixel_height
                / 10000,
                min_corridor_width=int(config.min_corridor_width)
                * max(pixel_width, pixel_height),
                max_search_distance=int(config.max_search_distance)
                * max(pixel_width, pixel_height),
                grid_resolution=max(pixel_width, pixel_height, 1.0),
            )
        else:
            normalized = replace(
                config,
                grid_resolution=max(pixel_width, pixel_height, 1.0)
                / (0.3048 if config.units == "imperial" else 1.0),
            )
        params = _params(normalized, layer)
        # The legacy raster bridge measures/masks in the raster CRS, which must be metre-based.
        if abs(unit_factor - 1) > 1e-9:
            raise TerraLinkError(
                "Raster analysis currently requires a metre-based projected CRS"
            )
        params["analysis_crs_authid"] = crs.to_string()
        params["raster_allow_bottlenecks"] = config.allow_bottlenecks
        if obstacles.any():
            params.update(
                obstacle_enabled=True,
                _raster_obstacle_mask=obstacles,
                _raster_obstacle_gt=ds.transform.to_gdal(),
            )
        raster_source = {
            "profile": ds.profile.copy(),
            "transform": ds.transform,
            "shape": data.shape,
            "crs": crs.to_string(),
            "obstacles": obstacles,
        }
    return _execute(
        layer,
        output_dir,
        config,
        params,
        [input_path],
        progress=progress,
        raster_source=raster_source,
    )


def _verify_raster_barriers(gpkg, layer, source):
    if not source["obstacles"].any():
        return
    from rasterio.windows import from_bounds, Window, transform as window_transform
    from pyproj import Transformer
    from shapely.ops import transform

    meta, _, geometries, _ = raw.read(str(gpkg), layer=layer)
    convert = Transformer.from_crs(meta["crs"], source["crs"], always_xy=True)
    height, width = source["shape"]
    for wkb in geometries:
        geometry = transform(convert.transform, from_wkb(wkb))
        window = from_bounds(*geometry.bounds, source["transform"])
        x0 = max(0, math.floor(window.col_off))
        y0 = max(0, math.floor(window.row_off))
        x1 = min(width, math.ceil(window.col_off + window.width))
        y1 = min(height, math.ceil(window.row_off + window.height))
        if x1 <= x0 or y1 <= y0:
            continue
        blocked = source["obstacles"][y0:y1, x0:x1]
        if not blocked.any():
            continue
        affine = window_transform(Window(x0, y0, x1 - x0, y1 - y0), source["transform"])
        for polygon, value in shapes(
            blocked.astype("uint8"), mask=blocked, transform=affine
        ):
            if value and geometry.intersection(shape(polygon)).area > 1e-7:
                raise TerraLinkError(
                    "Final corridor output overlaps an impassable raster cell"
                )


def _write_display_rasters(gpkg, corridor_layer, output, source):
    from pyproj import Transformer
    from shapely.ops import transform

    outputs = []
    for layer, name in [
        (corridor_layer, "corridors.tif"),
        ("Contiguous Areas", "networks.tif"),
    ]:
        meta, _, geometries, _ = raw.read(str(gpkg), layer=layer)
        convert = Transformer.from_crs(meta["crs"], source["crs"], always_xy=True)
        objects = [
            (transform(convert.transform, from_wkb(g)), i + 1)
            for i, g in enumerate(geometries)
        ]
        arr = (
            rasterize(
                objects,
                out_shape=source["shape"],
                transform=source["transform"],
                fill=0,
                dtype="int32",
            )
            if objects
            else np.zeros(source["shape"], dtype="int32")
        )
        profile = source["profile"].copy()
        profile.update(driver="GTiff", count=1, dtype="int32", nodata=0, compress="lzw")
        with rasterio.open(output / name, "w", **profile) as ds:
            ds.write(arr, 1)
            ds.update_tags(
                TERRALINK_DISPLAY_ONLY="true",
                VALUE_MEANING="feature_id; not habitat area or efficiency",
            )
        outputs.append(name)
    return outputs
