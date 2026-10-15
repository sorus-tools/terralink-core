"""Optional local/self-hosted HTTP service for the existing TerraLink browser tool."""

from collections import defaultdict, deque
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from threading import Lock
import time
import uuid
import zipfile

from . import ALGORITHM_PROFILE, __version__
from .models import RunConfig, STRATEGIES, TerraLinkError


def _values(value):
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return tuple(float(v.strip()) for v in value.split(",") if v.strip())
    return tuple(float(v) for v in value)


def _config(params, mode, has_barriers=False):
    """Translate the established online form names into explicit public API units."""
    from dataclasses import fields
    from ._engine.analysis_vector import VectorRunParams

    options = {
        key: params[key]
        for key in {f.name for f in fields(VectorRunParams)}
        if key in params
    }
    reserved = {
        "budget_area",
        "min_patch_size",
        "min_corridor_width",
        "max_search_distance",
        "grid_resolution",
        "unit_system",
        "output_name",
        "obstacle_enabled",
        "obstacle_layer_ids",
        "vector_routing_enabled",
    }
    options = {key: value for key, value in options.items() if key not in reserved}
    shared = {
        "strategy": params.get("strategy", "most_connected_networks"),
        "routing_enabled": params.get("vector_routing_enabled", has_barriers),
        "engine_options": options,
        "analysis_crs": params.get("analysis_crs"),
    }
    if mode == "raster":
        patch_range = None
        if (
            params.get("raster_patch_range_lower") is not None
            and params.get("raster_patch_range_upper") is not None
        ):
            patch_range = (
                float(params["raster_patch_range_lower"]),
                float(params["raster_patch_range_upper"]),
            )
        obstacle_range = None
        if (
            params.get("raster_obstacle_range_lower") is not None
            and params.get("raster_obstacle_range_upper") is not None
        ):
            obstacle_range = (
                float(params["raster_obstacle_range_lower"]),
                float(params["raster_obstacle_range_upper"]),
            )
        return RunConfig(
            **shared,
            budget_area=float(params.get("raster_budget", 200)),
            min_patch_size=float(params.get("raster_min_patch_size", 1)),
            min_corridor_width=float(params.get("raster_min_width", 2)),
            max_search_distance=float(params.get("raster_max_search", 80)),
            units=params.get("raster_units", "pixels"),
            patch_values=_values(
                params.get("raster_patch_values", "" if patch_range else "1")
            ),
            obstacle_values=_values(params.get("raster_obstacle_values", "")),
            patch_range=patch_range,
            obstacle_range=obstacle_range,
            patch_connectivity=int(params.get("raster_patch_connectivity", 4)),
            allow_bottlenecks=params.get("raster_allow_bottlenecks", True),
        )
    return RunConfig(
        **shared,
        budget_area=float(params.get("budget_area", 2)),
        min_patch_size=float(params.get("min_patch_size", 0.01)),
        min_corridor_width=float(params.get("min_corridor_width", 20)),
        max_search_distance=float(params.get("max_search_distance", 800)),
        grid_resolution=float(params.get("grid_resolution", 10)),
        units=params.get("unit_system", "metric"),
    )


def _expand_upload(path, maximum):
    if path.suffix.lower() != ".zip":
        return path
    directory = path.parent / (path.stem + "_expanded")
    directory.mkdir()
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 500 or sum(item.file_size for item in members) > maximum * 4:
            raise TerraLinkError("Archive expands beyond the file-count or size limit")
        for member in members:
            candidate = Path(member.filename)
            if (
                candidate.is_absolute()
                or ".." in candidate.parts
                or "\\" in member.filename
                or stat.S_ISLNK(member.external_attr >> 16)
            ):
                raise TerraLinkError("Archive contains an unsafe path or symbolic link")
            resolved = (directory / candidate).resolve()
            if not resolved.is_relative_to(directory.resolve()):
                raise TerraLinkError("Archive path leaves its extraction directory")
        archive.extractall(directory)
    datasets = [
        p
        for p in directory.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".shp", ".gpkg", ".geojson", ".json", ".kml"}
        and "__MACOSX" not in p.parts
    ]
    if len(datasets) != 1:
        raise TerraLinkError(
            "Archive must contain exactly one supported vector dataset"
        )
    return datasets[0]


def _preview_geojson(path, output, *, layer=None, values=None, value_range=None):
    from pyogrio import raw
    from pyproj import Transformer
    from shapely import from_wkb
    from shapely.geometry import mapping, shape, box
    from shapely.ops import transform
    from .api import _json_safe

    features = []
    if Path(path).suffix.lower() in {".tif", ".tiff"}:
        import numpy as np
        import rasterio
        from rasterio.features import shapes

        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise TerraLinkError("Raster has no CRS")
            convert = Transformer.from_crs(ds.crs, "EPSG:4326", always_xy=True)
            if values or value_range is not None:
                if ds.width * ds.height > 40_000_000:
                    raise TerraLinkError("Raster preview exceeds the cell limit")
                data = ds.read(1, masked=True)
                raw_values = np.asarray(data)
                mask = np.isin(raw_values, values or ())
                if value_range is not None:
                    mask |= (raw_values >= value_range[0]) & (
                        raw_values <= value_range[1]
                    )
                mask &= ~np.ma.getmaskarray(data) & np.isfinite(raw_values)
                objects = [
                    shape(g)
                    for g, v in shapes(
                        mask.astype("uint8"), mask=mask, transform=ds.transform
                    )
                    if v == 1
                ]
            else:
                objects = [box(*ds.bounds)]
            for geometry in objects:
                features.append(
                    {
                        "type": "Feature",
                        "properties": {"preview_only": True},
                        "geometry": mapping(transform(convert.transform, geometry)),
                    }
                )
    else:
        meta, _, geometries, arrays = raw.read(
            str(path), layer=layer, max_features=10001
        )
        if len(geometries) > 10000:
            raise TerraLinkError(
                "Preview exceeds 10,000 features; analytical output remains available"
            )
        if not meta.get("crs"):
            raise TerraLinkError("Vector input has no CRS")
        convert = Transformer.from_crs(meta["crs"], "EPSG:4326", always_xy=True)
        for i, geom in enumerate(geometries):
            if geom is not None:
                props = {
                    str(key): _json_safe(array[i])
                    for key, array in zip(meta["fields"], arrays)
                }
                features.append(
                    {
                        "type": "Feature",
                        "properties": props,
                        "geometry": mapping(
                            transform(convert.transform, from_wkb(geom))
                        ),
                    }
                )
    Path(output).write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def create_app(configuration=None):
    from flask import Flask, jsonify, request, send_from_directory, url_for
    from werkzeug.exceptions import RequestEntityTooLarge
    from werkzeug.utils import secure_filename

    static = Path(__file__).with_name("web_static")
    app = Flask(__name__, static_folder=None)
    app.config.update(
        STORAGE_ROOT=os.environ.get(
            "TERRALINK_STORAGE", str(Path(tempfile.gettempdir()) / "terralink-core")
        ),
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
        MAX_RUN_SECONDS=int(os.environ.get("MAX_RUN_SECONDS", "300")),
        RUNS_PER_HOUR=5,
        PREVIEWS_PER_HOUR=30,
        RETENTION_HOURS=24,
        ALLOWED_ORIGINS={
            value.strip()
            for value in os.environ.get("ALLOWED_ORIGINS", "").split(",")
            if value.strip()
        },
    )
    app.config.update(configuration or {})
    storage = Path(app.config["STORAGE_ROOT"]).resolve()
    storage.mkdir(parents=True, exist_ok=True)
    busy = Lock()
    rate_lock = Lock()
    rates = defaultdict(deque)

    @app.before_request
    def check_origin():
        origin = request.headers.get("Origin")
        if (
            origin
            and origin.rstrip("/") != request.host_url.rstrip("/")
            and origin not in app.config["ALLOWED_ORIGINS"]
        ):
            return jsonify(error="Origin is not allowed"), 403

    @app.after_request
    def cors(response):
        origin = request.headers.get("Origin")
        if origin in app.config["ALLOWED_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "POST,GET,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Vary"] = "Origin"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return jsonify(error="Upload exceeds the configured size limit"), 413

    @app.errorhandler(TerraLinkError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    def rate_limit(kind):
        maximum = app.config["RUNS_PER_HOUR" if kind == "run" else "PREVIEWS_PER_HOUR"]
        now = time.time()
        key = (request.remote_addr, kind)
        with rate_lock:
            queue = rates[key]
            while queue and queue[0] < now - 3600:
                queue.popleft()
            if len(queue) >= maximum:
                return True
            queue.append(now)
        return False

    def save_upload(file, directory):
        if file is None or not file.filename:
            raise TerraLinkError("No input file provided")
        name = secure_filename(file.filename)
        if not name or Path(name).suffix.lower() not in {
            ".zip",
            ".geojson",
            ".json",
            ".gpkg",
            ".kml",
            ".tif",
            ".tiff",
        }:
            raise TerraLinkError("Unsupported input file type")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        file.save(path)
        return _expand_upload(path, app.config["MAX_CONTENT_LENGTH"])

    def new_job():
        for item in storage.iterdir():
            if (
                item.is_dir()
                and re.fullmatch("[0-9a-f]{32}", item.name)
                and time.time() - item.stat().st_mtime
                > app.config["RETENTION_HOURS"] * 3600
            ):
                shutil.rmtree(item)
        jobid = uuid.uuid4().hex
        job = storage / jobid
        job.mkdir()
        return jobid, job

    def preview_entry(jobid, job, input_path, params, obstacle_paths=(), result=None):
        output = job / "results"
        output.mkdir(exist_ok=True)
        entries = {}
        warnings = []
        specs = [
            ("input", input_path, None, _values(params.get("raster_patch_values", "")))
        ]
        specs.extend(
            ("obstacles" if i == 0 else f"obstacles_{i + 1}", p, None, None)
            for i, p in enumerate(obstacle_paths)
        )
        if result:
            specs.extend(
                [
                    (
                        "corridors",
                        result["corridors_path"],
                        result["corridor_layer"],
                        None,
                    ),
                    (
                        "contiguous",
                        result["corridors_path"],
                        result["network_layer"],
                        None,
                    ),
                ]
            )
        for key, path, layer, values in specs:
            try:
                name = f"{key}_preview.geojson"
                value_range = None
                if (
                    key == "input"
                    and params.get("raster_patch_range_lower") is not None
                    and params.get("raster_patch_range_upper") is not None
                ):
                    value_range = (
                        float(params["raster_patch_range_lower"]),
                        float(params["raster_patch_range_upper"]),
                    )
                _preview_geojson(
                    path,
                    output / name,
                    layer=layer,
                    values=values,
                    value_range=value_range,
                )
                entries[key] = {
                    "type": "vector",
                    "url": url_for("download", job_id=jobid, filename=name),
                }
            except Exception as exc:
                warnings.append(f"{key} preview: {exc}")
        return entries, warnings

    @app.get("/healthz")
    @app.get("/api/healthz")
    def health():
        return "ok"

    @app.get("/capabilities")
    @app.get("/api/capabilities")
    def capabilities():
        return jsonify(
            version=__version__,
            algorithm_profile=ALGORITHM_PROFILE,
            strategies=STRATEGIES,
            max_upload_bytes=app.config["MAX_CONTENT_LENGTH"],
            max_run_seconds=app.config["MAX_RUN_SECONDS"],
            retention_hours=app.config["RETENTION_HOURS"],
            status="alpha",
        )

    @app.get("/download/<job_id>/<filename>")
    def download(job_id, filename):
        if (
            not re.fullmatch("[0-9a-f]{32}", job_id)
            or Path(filename).name != filename
            or filename.startswith(".")
        ):
            return jsonify(error="Invalid download path"), 400
        response = send_from_directory(
            storage / job_id / "results", filename, as_attachment=True
        )
        if filename.endswith(".geojson"):
            response.mimetype = "application/geo+json"
        return response

    @app.route("/preview", methods=["POST", "OPTIONS"])
    @app.route("/api/preview", methods=["POST", "OPTIONS"])
    def preview():
        if request.method == "OPTIONS":
            return "", 204
        if rate_limit("preview"):
            return jsonify(error="Preview rate limit exceeded"), 429
        try:
            params = json.loads(request.form.get("params", "{}"))
            if not isinstance(params, dict):
                raise TerraLinkError("params must be a JSON object")
            jobid, job = new_job()
            source = save_upload(request.files.get("file"), job / "uploads")
            obstacles = [
                save_upload(file, job / f"obstacles/{i}")
                for i, file in enumerate(request.files.getlist("obstacle_files"))
            ]
            entries, warnings = preview_entry(jobid, job, source, params, obstacles)
            shutil.rmtree(job / "uploads")
            shutil.rmtree(job / "obstacles", ignore_errors=True)
            return jsonify(jobId=jobid, previews=entries, preview_errors=warnings)
        except (ValueError, TypeError, zipfile.BadZipFile) as exc:
            return jsonify(error=str(exc)), 400

    @app.route("/run", methods=["POST", "OPTIONS"])
    @app.route("/api/run", methods=["POST", "OPTIONS"])
    def run():
        if request.method == "OPTIONS":
            return "", 204
        if rate_limit("run"):
            return jsonify(error="Run rate limit exceeded"), 429
        if not busy.acquire(blocking=False):
            return jsonify(error="Server is busy; retry after the current run"), 429
        job = None
        try:
            params = json.loads(request.form.get("params", "{}"))
            if not isinstance(params, dict):
                raise TerraLinkError("params must be a JSON object")
            jobid, job = new_job()
            source = save_upload(request.files.get("file"), job / "uploads")
            mode = params.get("layer_type") or (
                "raster" if source.suffix.lower() in {".tif", ".tiff"} else "vector"
            )
            if mode not in {"raster", "vector"}:
                raise TerraLinkError("layer_type must be vector or raster")
            obstacles = [
                save_upload(file, job / f"obstacles/{i}")
                for i, file in enumerate(request.files.getlist("obstacle_files"))
            ]
            config = _config(params, mode, bool(obstacles))
            payload = {
                "mode": mode,
                "input": str(source),
                "obstacles": [str(p) for p in obstacles],
                "layer": params.get("input_layer_name") or params.get("layer_name"),
                "parameters": config.to_dict(),
            }
            (job / "request.json").write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "terralink_core.cli",
                    "run",
                    "--config",
                    str(job / "request.json"),
                    "--output",
                    str(job / "results"),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=app.config["MAX_RUN_SECONDS"],
            )
            if completed.returncode:
                try:
                    message = json.loads(completed.stderr.splitlines()[-1])["message"]
                except (ValueError, IndexError, KeyError):
                    message = "Analysis failed; check server logs"
                raise TerraLinkError(message)
            result = json.loads(completed.stdout)
            entries, warnings = preview_entry(
                jobid, job, source, params, obstacles, result
            )
            outputs = [
                {
                    "filename": p.name,
                    "label": p.name,
                    "url": url_for("download", job_id=jobid, filename=p.name),
                }
                for p in sorted((job / "results").iterdir())
                if p.is_file() and "_preview." not in p.name
            ]
            stats = result["stats"]
            # Expose artifact names rather than server filesystem layout.
            stats = {
                key: Path(value).name
                if isinstance(value, str) and str(job) in value
                else value
                for key, value in stats.items()
            }
            return jsonify(
                jobId=jobid,
                outputs=outputs,
                previews=entries,
                preview_errors=warnings,
                stats=stats,
                implementation_version=__version__,
                algorithm_profile=ALGORITHM_PROFILE,
            )
        except subprocess.TimeoutExpired:
            return jsonify(error="Run exceeded the configured execution limit"), 504
        except (ValueError, TypeError, KeyError, zipfile.BadZipFile) as exc:
            return jsonify(error=str(exc)), 400
        finally:
            if job:
                shutil.rmtree(job / "uploads", ignore_errors=True)
                shutil.rmtree(job / "obstacles", ignore_errors=True)
                (job / "request.json").unlink(missing_ok=True)
            busy.release()

    @app.get("/")
    def index():
        from flask import redirect

        return redirect("/tools/terralink-online/")

    @app.get("/<path:path>")
    def frontend(path):
        target = path + "index.html" if path.endswith("/") else path
        return send_from_directory(static, target)

    return app
