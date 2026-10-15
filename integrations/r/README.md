# Two explicit R routes

The existing [terralink R package](https://github.com/sorus-tools/terralink-r) is
native R and remains usable without Python or QGIS. Its measured compatibility
with the extracted reference is recorded in `conformance/reports/r-native.md`.

For R users who deliberately want the exact shared Python engine, this repository
also supplies an optional sourceable bridge. It requires an installed core CLI and
`jsonlite`; with `sf` installed it returns corridor/network objects directly.
It is not an automatic backend switch or an already released R-package function.

```r
source("integrations/r/terralink_core.R")
result <- terralink_core_run(
  input = "conformance/fixtures/patches.geojson",
  output_dir = "run-output/from-r",
  parameters = list(
    strategy = "most_connected_networks", budget_area = 2,
    min_patch_size = 0.01, min_corridor_width = 20,
    max_search_distance = 800, analysis_crs = "EPSG:32631"
  ),
  executable = ".venv/bin/terralink" # Windows: .venv/Scripts/terralink.exe
)
plot(sf::st_geometry(result$corridors))
result$manifest$algorithm_profile
```

This bridge shares implementation behavior with Python/CLI/web. It does not
establish that the independent native R implementation produces the same geometry.
