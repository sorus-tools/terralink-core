# Optional, explicit R access to the shared Python engine.
# This does not replace or change the native terralink R package.

terralink_core_run <- function(input, output_dir, parameters, mode = c("vector", "raster"),
                              obstacles = NULL, layer = NULL,
                              executable = Sys.which("terralink")) {
  mode <- match.arg(mode)
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Install jsonlite to use this optional bridge.")
  if (!nzchar(executable) || !file.exists(executable)) stop("An installed TerraLink core CLI is required; supply executable explicitly if it is not on PATH.")
  if (!is.list(parameters) || is.null(names(parameters))) stop("parameters must be a named list of RunConfig settings.")
  input <- normalizePath(path.expand(input), winslash = "/", mustWork = TRUE)
  if (!is.null(obstacles)) obstacles <- vapply(obstacles, normalizePath, character(1), winslash = "/", mustWork = TRUE)
  output_dir <- path.expand(output_dir)
  dir.create(dirname(output_dir), recursive = TRUE, showWarnings = FALSE)
  output_dir <- file.path(normalizePath(dirname(output_dir), winslash = "/", mustWork = TRUE), basename(output_dir))
  for (key in intersect(names(parameters), c("patch_values", "obstacle_values", "patch_range", "obstacle_range"))) {
    parameters[[key]] <- I(as.numeric(parameters[[key]]))
  }
  request <- list(mode = mode, input = input, parameters = parameters)
  if (length(obstacles)) request$obstacles <- I(obstacles)
  if (!is.null(layer)) request$layer <- layer
  scratch <- tempfile("terralink_core_request_")
  dir.create(scratch)
  on.exit(unlink(scratch, recursive = TRUE), add = TRUE)
  config_path <- file.path(scratch, "request.json")
  stdout_path <- file.path(scratch, "stdout.json")
  stderr_path <- file.path(scratch, "stderr.txt")
  jsonlite::write_json(request, config_path, auto_unbox = TRUE, null = "null", digits = NA)
  status <- system2(executable, c("run", "--config", shQuote(config_path), "--output", shQuote(output_dir)),
                    stdout = stdout_path, stderr = stderr_path)
  if (status != 0) stop(paste(readLines(stderr_path, warn = FALSE), collapse = "\n"))
  result <- jsonlite::read_json(stdout_path, simplifyVector = TRUE)
  result$manifest <- jsonlite::read_json(result$manifest_path, simplifyVector = TRUE)
  if (requireNamespace("sf", quietly = TRUE)) {
    result$corridors <- sf::st_read(result$corridors_path, layer = result$corridor_layer, quiet = TRUE)
    result$networks <- sf::st_read(result$corridors_path, layer = result$network_layer, quiet = TRUE)
  }
  class(result) <- c("terralink_core_result", "list")
  result
}
