# Metrics and analytical output

The selected corridor GeoPackage contains corridor polygons and connected network
polygons, source/internal patch identifiers, area/efficiency values, redundancy
and chain annotations. Nullable chain identifiers remain NULL, not zero. Areas in
attribute names ending `_ha` or `_ac` follow the displayed unit system; geometry
coordinates follow the input CRS. Full field precision may exceed display rounding.

`stats` and `metrics.json` retain named PRE/POST values from the reference engine,
including connected habitat area, largest network size, normalized mesh and LCC,
probability of connectivity, effective graph resistance, and landscape fluidity.
The readable landscape report also includes raster-derived landscape summaries;
its effective rasterization resolution is recorded separately. Fields ending
`_exact` distinguish the reference engine's graph/component calculations from
approximate raster reports; they are not a claim of ecological truth.

Raster display GeoTIFFs in this standalone preview use feature IDs, with zero
as background. They do not reproduce the independent R package's connected-area
or efficiency-valued raster display assignment. Use the analytical vector bundle,
its attributes and the explicit metrics for quantitative interpretation.

Errors in report generation, output export, feature-count consistency, budget
feasibility, or final barrier checks fail the library run. This is stricter than
the legacy UI's tolerance of some export/report failures. Output directories must
be new or empty; reruns do not silently overwrite earlier analyses.
