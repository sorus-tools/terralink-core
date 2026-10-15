# Reproducible reference comparisons

The fixtures are synthetic and redistributable. `tools/generate_fixtures.py`
documents their construction, while `fixture-hashes.json` fixes the exact files
used to capture the initial baseline. Do not regenerate raster binaries casually
and assume their byte hashes will match across GDAL versions.

The 16 `expected/*.json` files were captured from released QGIS 1.8.3 source with
the supplied headless runner. They retain analytical geometry and selected metrics,
not private logs or local file paths. Source revision and tolerances are explicit.

```sh
QGIS_PYTHON conformance/runners/capture_qgis.py --plugin-parent /path/containing/TerraLink --output /temporary/capture
python tools/freeze_qgis_baselines.py /temporary/capture
python -m pytest tests/test_conformance.py -q
```

Changing expected outputs requires review and a documented reason. Regression
agreement establishes implementation behavior on these cases, not ecological
validation or universal optimizer equivalence.

For native R, with its existing source and dependencies installed:

```sh
Rscript conformance/runners/capture_r.R /path/to/terralink-r conformance/fixtures /temporary/r-capture
python tools/report_r_compatibility.py /temporary/r-capture
```

The R runner disables its experimental QGIS bridge and requests the same 4-cell
connectivity as the reference raster fixture. Reports must distinguish the local
working source fingerprint from its parent Git revision or registry release.
