# Parameters and units

`RunConfig` rejects unknown constructor arguments and unknown/reserved engine
options. Strategy keys are explicit; misspellings do not silently fall back.

| Setting | Metric | Imperial | Raster pixels |
|---|---|---|---|
| `budget_area` | hectares | acres | whole cells |
| `min_patch_size` | hectares | acres | whole cells |
| `min_corridor_width` | metres | feet | whole multiples of the larger cell dimension |
| `max_search_distance` | metres | feet | whole multiples of the larger cell dimension |
| `grid_resolution` | metres | feet | inherited raster cell size |

Distances are normalized to metres and the inherited vector engine's area
parameters to hectares. The current extraction retains that internal area
convention; normalized values and original settings are both recorded. Budgets
are restoration areas, not financial costs. Non-integral pixel quantities are
rejected explicitly rather than silently truncated. Use measured units for
fractional widths/areas.

The default vector strategy is MCN B, routing is disabled unless requested, and
the default patch connectivity is 4. The extracted online form intentionally
retains its existing UI defaults, including MCN A and 8-neighbor raster patches;
the request records those values. Do not compare runs without normalizing defaults.

Vector input requires a declared CRS and polygon/multipolygon features. An
explicit `analysis_crs` must be projected with metre axes. Otherwise the inherited
centroid-based UTM choice is recorded; broad/polar geographic extents need an
explicit suitable projected CRS. Measurements use the analysis CRS; output vector
geometry is returned in the input CRS.

Raster input requires a projected metre-based north-up grid in this preview.
Non-square cells use their actual area and larger dimension for pixel lengths,
matching the inherited bridge. Rotated grids and non-metre axes are rejected.
Selected bands, class values/ranges, NoData mask, and 4/8 connectivity are explicit.
When values and a range are both supplied their habitat membership is the union;
obstacle membership excludes selected habitat.

Advanced `engine_options` expose recognized fields of the preserved vector
configuration. They are intended for reproducible research, not a promise of
stable internals. They may not override reserved units/budget/input/output fields.
Computation limits and any inherited early-stop diagnostics remain visible.
