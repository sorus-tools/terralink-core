# Run native R without the optional QGIS bridge; writes a measured compatibility report.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) stop("Usage: Rscript capture_r.R R_SOURCE FIXTURES OUTPUT")
Sys.unsetenv("TERRALINK_EXPERIMENTAL_QGIS_RASTER_BRIDGE")
pkgload::load_all(args[[1]], quiet = TRUE)
fixtures <- normalizePath(args[[2]])
out <- args[[3]]
dir.create(out, recursive = TRUE, showWarnings = FALSE)
strategies <- c("most_connected_networks", "most_connected_networks_2", "largest_single_network", "landscape_fluidity")
report <- list()
for (case in c("plain", "gap", "sealed", "raster")) {
  for (strategy in strategies) {
    key <- paste(case, strategy, sep = "_")
    item <- tryCatch({
      if (case == "raster") {
        result <- terralink::terralink_raster(
          raster = file.path(fixtures, "habitat.tif"), patch_values = 1,
          budget = 200, min_patch_size = 1, min_corridor_width = 2,
          max_search_distance = 80, units = "pixels", patch_connectivity = 4, strategy = strategy,
          progress = FALSE, verbose = 0
        )
      } else {
        barriers <- if (case == "plain") NULL else file.path(fixtures, paste0("barrier_", if (case == "gap") "gap" else "sealed", ".geojson"))
        result <- terralink::terralink_vector(
          patches = file.path(fixtures, "patches.geojson"), budget = 2,
          min_patch_size = 0.01, min_corridor_width = 20,
          max_search_distance = 800, obstacle_layers = barriers,
          obstacle_resolution = 10, units = "metric", strategy = strategy,
          progress = FALSE, verbose = 0
        )
      }
      rows <- result$corridors
      geometry <- if (inherits(rows, "sf")) as.character(sf::st_as_text(sf::st_geometry(rows), digits = 12)) else character()
      properties <- if (inherits(rows, "sf")) sf::st_drop_geometry(rows) else rows
      list(implementation = "r-native", case = case, strategy = strategy,
           package_version = as.character(utils::packageVersion("terralink")),
           summary = result$summary, stats = result$strategy_stats, metrics = result$metrics,
           corridors = properties, geometry = geometry)
    }, error = function(e) list(implementation = "r-native", case = case, strategy = strategy, error = conditionMessage(e)))
    jsonlite::write_json(item, file.path(out, paste0(key, ".json")), pretty = TRUE, auto_unbox = TRUE, null = "null", digits = 15)
    report[[key]] <- list(error = item$error, corridor_count = length(item$geometry))
    cat(key, if (is.null(item$error)) paste(length(item$geometry), "corridors") else item$error, "\n")
  }
}
jsonlite::write_json(report, file.path(out, "capture-summary.json"), pretty = TRUE, auto_unbox = TRUE, null = "null")
