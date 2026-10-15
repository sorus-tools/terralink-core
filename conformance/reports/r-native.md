# Native R compatibility capture

0 of 16 cases agree on selected corridor geometry and normalized budget.
10 of 16 agree on selected patch memberships and normalized budget; this weaker agreement does not establish identical corridor placement.

This capture uses the identified working R source, not a claim about every public R release. Native R remains independent of Python/QGIS.

| Case | R corridors | QGIS corridors | Budget difference (ha) | Geometry/budget agreement |
|---|---:|---:|---:|---|
| gap_landscape_fluidity | 3 | 3 | 0.0063480392 | Difference |
| gap_largest_single_network | 3 | 3 | 0.0063480392 | Difference |
| gap_most_connected_networks | 2 | 2 | 0.0088259486 | Difference |
| gap_most_connected_networks_2 | 2 | 2 | 0.0088259486 | Difference |
| plain_landscape_fluidity | 3 | 3 | -1.2522428e-11 | Difference |
| plain_largest_single_network | 3 | 3 | -1.2522428e-11 | Difference |
| plain_most_connected_networks | 2 | 2 | -1.6741608e-11 | Difference |
| plain_most_connected_networks_2 | 2 | 2 | -1.6741608e-11 | Difference |
| raster_landscape_fluidity | 4 | 3 | 0.34815125 | Difference |
| raster_largest_single_network | 4 | 3 | 0.73136548 | Difference |
| raster_most_connected_networks | 2 | 2 | 2.8393954e-12 | Difference |
| raster_most_connected_networks_2 | 2 | 2 | 2.8393954e-12 | Difference |
| sealed_landscape_fluidity | 1 | 1 | 9.7094555e-13 | Difference |
| sealed_largest_single_network | 1 | 1 | 9.7094555e-13 | Difference |
| sealed_most_connected_networks | 1 | 1 | 9.7094555e-13 | Difference |
| sealed_most_connected_networks_2 | 1 | 1 | 9.7094555e-13 | Difference |

Matching cases are regression evidence for these settings only. Gap routing and raster LSN/LF differences require further native R alignment before claiming a shared numerical profile.
Even equal-budget vector cases can choose a different boundary location between equally distant patches. Strict polygon comparisons retain that difference rather than widening tolerances or treating similar scores as spatial equivalence.

See `r-native.json` for source fingerprint, exact measurements, and comparison scope.
