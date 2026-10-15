# Standalone HTTP service

Install `.[web]`, then use `terralink serve`. The default bind is loopback, storage
is local, execution timeout is 300 seconds, upload size is 50 MiB, and job storage
expires after 24 hours (cleanup runs when requests create a new job). Configure
`TERRALINK_STORAGE`, `MAX_RUN_SECONDS`, and comma-separated `ALLOWED_ORIGINS` as
needed. Same-origin use needs no CORS configuration.

Existing endpoints `/healthz`, `/preview`, and `/run` also have `/api/` aliases.
POST a multipart `file`, a JSON `params` field, and optional `obstacle_files`.
Vector settings use the existing `budget_area`, `min_corridor_width`,
`max_search_distance`, `min_patch_size`, `unit_system`, and `grid_resolution` names.
Raster settings use `raster_budget`, `raster_min_width`, `raster_max_search`,
`raster_min_patch_size`, `raster_units`, and `raster_patch_values`; optional ranges,
obstacle values, and 4/8 connectivity are supported. `/capabilities` identifies
the engine/profile, strategies, and effective limits.

Responses preserve `jobId`, `outputs`, `previews`, `preview_errors`, and `stats`.
Download links use `/download/JOB/FILENAME`; previews are display GeoJSON in
EPSG:4326. Full-resolution analytical geometries are in the GeoPackage. A preview
error is reported separately from analytical output success.

Each analysis runs in a child process that is terminated on timeout. A process
accepts one analysis at a time; concurrent requests receive a busy response.
Default throttles are five runs and thirty previews per hour per client address.
These throttles are per application process, not a distributed quota system.
Deploy behind an appropriate reverse proxy, use one WSGI worker per intended
analysis slot, and provision memory/CPU limits at the hosting boundary. Do not
publish the development Flask server as a hardened Internet service.

Uploads, extracted archives, and request settings are temporary; downloadable
results remain in local job storage until expiry. Treat the random job URL as a
download capability: there is no user-account authorization layer in this alpha.
For sensitive hosted data add an authenticated access boundary and an explicit
retention policy. For local use the default loopback binding avoids sharing.

Archive extraction checks paths, symlinks, file count and expanded size. User
supplied URLs and arbitrary server paths are not accepted as uploaded inputs.
Cloud object storage is not implemented by this new service yet; the existing
production QGIS service remains a separate deployment until migration is accepted.

For WSGI, install a server such as Gunicorn separately and use
`gunicorn --chdir services/http --workers 1 --threads 2 --timeout 330 app:app`.
No Docker or Google Cloud account is required for local operation.
