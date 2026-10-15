# Algorithm profile: QGIS 1.8.3 extraction (alpha)

The reference is TerraLink QGIS revision
`2cb4a568e8990d7834019ce9bdbdfb7f3ae893f4`. The active candidate generation,
selection, rescue/refill, final admission, graph metrics, and network construction
remain in `_engine/analysis_vector.py`. `source-provenance.json` records original
hashes. The standalone adaptation replaces QGIS geometry with a narrowly tested
Shapely/PyProj facade and QGIS/GDAL application I/O with Rasterio/Pyogrio.

Polygon inputs are transformed to the analysis CRS, repaired where supported,
and intersecting habitat geometries are grouped into patches. Small patches are
filtered. Spatial search, boundary terminals, direct joins, optional grid routing,
chains, and rescue searches provide candidate corridors. Centerlines are buffered
to corridor width; endpoint/intermediate habitat, impassable overlaps and costs
are handled by the preserved finalization/admission rules. The selected set is
then annotated, checked and exported along with connected-network geometries.

Raster inputs select habitat/obstacle classes or ranges, respect NoData, polygonize
habitat using explicit 4/8 connectivity, and invoke that vector pipeline. Raster
obstacles remain a width-aware mask. The standalone preview additionally performs
an independent final overlap check against vector barriers or blocked raster-cell
polygons before returning a successful result.

MCN A (`most_connected_networks_2`) prioritizes component-pair value; MCN B
(`most_connected_networks`) prioritizes habitat recruited into connected networks;
LSN concentrates on a dominant network; LF uses graph movement/resistance and
redundancy objectives. Machine keys are deliberately retained despite their
historical A/B naming. Older strategy names are not silently remapped by the new
API; provide a current key.

Candidate caps, exact/beam branches, rescue/refill behavior, and wall-clock limits
are inherited. An optimizer's `proven_optimal` statistic applies to its defined
candidate problem, not all conceivable geographical corridors or ecological
outcomes. Fixed seeds do not remove machine-dependent wall-clock truncation.

The frozen suite is regression evidence on specified inputs and settings. It is
not observational validation, a universal optimality result, or proof of agreement
with the independent R implementation on all inputs.
