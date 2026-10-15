# TerraLink

**Open-source ecological connectivity and habitat-corridor planning.**

TerraLink compares corridor scenarios under restoration-area budgets, corridor
widths, search distances, and impassable barriers. This repository is the home
for the standalone Python engine, command line, reusable online tool, method
contracts, and cross-implementation reference tests.

**Status: experimental `0.1.0a1`.** The active QGIS 1.8.3 algorithm has been
extracted into a QGIS-free runtime. All four modes are compared against frozen
QGIS outputs on the bundled synthetic cases. This is not a claim of identical
behavior on every landscape or validation of animal movement predictions.

| Use TerraLink through | Where to start |
|---|---|
| QGIS | [Existing plugin](https://plugins.qgis.org/plugins/TerraLink/) · [source](https://github.com/sorus-tools/TerraLink) |
| R / RStudio | [Native R package](https://github.com/sorus-tools/terralink-r) |
| Python / notebooks | The API below |
| Command line | The JSON-configured CLI below |
| Browser / self-hosting | `terralink serve` after installing the web extra |

Native R remains independent of Python and QGIS. Its measured differences are
reported separately; do not assume the same result merely because strategy
names match. The existing hosted SORUS tool and stable QGIS installation are
not replaced automatically by installing this preview.

R users who explicitly want the shared Python engine can also use the
[optional R bridge](integrations/r/README.md), which returns `sf` objects when
available. The existing native R functions keep their independent runtime.

## Install from source

Python 3.11 or newer is required. No desktop GIS is required. The standalone
dependencies use Shapely, PyProj, Rasterio, and Pyogrio; their supported wheels
must be available for your Python/OS combination.

```sh
git clone https://github.com/sorus-tools/terralink-core.git
cd terralink-core
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[web,test]'
```

On Windows activate `.venv\Scripts\activate` instead. This preview is distributed
from GitHub/source artifacts; a PyPI release is not assumed.

## Python example

```python
from terralink_core import RunConfig, run_vector

settings = RunConfig(
    strategy="most_connected_networks",
    budget_area=2.0,          # hectares in metric mode
    min_patch_size=0.01,      # hectares
    min_corridor_width=20,    # metres
    max_search_distance=800,  # metres
    analysis_crs="EPSG:32631",
)
result = run_vector(
    "conformance/fixtures/patches.geojson",
    "run-output/python-example",  # must be new or empty
    settings,
)
print(result.corridors_path)
print(result.stats["budget_used_ha"])
```

Use `obstacles="barriers.gpkg"` and `routing_enabled=True` in the settings for
width-aware routing around vector obstacles. A selected line is checked again
after buffering; blocked candidates are rejected.

For a raster, call `run_raster()` with a GeoTIFF. Set `patch_values`, optional
`obstacle_values`, `patch_connectivity=4` or `8`, and units. Raster inputs are
polygonized and run through the same vector-selection backend. Pixel-mode
budgets and minimum sizes count cells; lengths count the larger cell dimension,
following the inherited bridge. Rotated grids and non-metre raster CRSs are
rejected explicitly in this preview. Raster display outputs contain feature IDs,
not connected-area or efficiency scores; the GeoPackage is the analytical output.

## Command line

```sh
terralink capabilities
terralink run --config examples/vector.json --output run-output/vector
terralink run --config examples/raster.json --output run-output/raster
```

Configuration input paths are relative to the JSON file. Errors return JSON on
stderr and a nonzero exit status. Successful runs write a GeoPackage with
corridors and connected networks, CSV summary, readable metrics, `metrics.json`,
`run.json` provenance/settings, and a run log. Raster runs also write display
GeoTIFFs. The area budget is not a monetary cost model.

## Online tool and self-hosting

```sh
terralink serve --host 127.0.0.1 --port 8080 --storage ./run-output/web-jobs
```

Open [the local tool](http://localhost:8080/tools/terralink-online/). The extracted
Astro interface is included in the Python wheel. It sends work to a local
standalone Python subprocess, not to QGIS. No SORUS account or cloud credentials
are needed. The browser uses Leaflet and an optional external basemap; analytical
computation remains on the server. See [HTTP/self-hosting](docs/http-service.md).

To rebuild the interface after editing `apps/web`:

```sh
cd apps/web
npm ci
cd ../..
python tools/build_web.py
```

## The four objectives

| Strategy key | Label | Planning emphasis |
|---|---|---|
| `most_connected_networks_2` | Most Connected Networks A | Component-pair value and useful joins into existing networks |
| `most_connected_networks` | Most Connected Networks B | Habitat area recruited into connected subnetworks |
| `largest_single_network` | Largest Single Network | One dominant connected network |
| `landscape_fluidity` | Landscape Fluidity | Graph-based movement efficiency and redundancy |

Selection includes inherited candidate limits, heuristics, and wall-clock limits.
A fixed seed does not guarantee identical time-limited searches across machines.
Landscape Fluidity is not a continuous current-flow solver. Compare plausible
scenarios and interpret results using habitat, species, and scale assumptions.

## Verification and development

```sh
python -m pytest -q
python -m build
```

Reference tests compare topology, budget, final polygon geometry, and selected
PRE/POST metrics, rather than only checking that code runs. Fixtures cover all
four modes on vector, barrier-gap, sealed-barrier, and raster inputs. Geometry
compatibility tests cover buffering, clipping, nearest points, CRS transforms,
indexing, smoothing, and QGIS-sensitive area arithmetic. See
[conformance](conformance/README.md) and [compatibility](spec/compatibility.md).

The extraction intentionally preserves the large active upstream implementation
under `_engine` while separating I/O and providing a narrow geometry backend.
Further internal decomposition can now be tested against that preserved behavior;
this alpha is not presented as the end of the architectural cleanup.

To build an isolated experimental QGIS plugin that uses this same algorithm:

```sh
python tools/build_qgis_preview.py --plugin-source ../TerraLink --output ./run-output/qgis-preview
```

The resulting `TerraLink.zip` bundles a pinned numerical engine and uses native
QGIS geometry. It does not install Shapely or Pyogrio into QGIS, modify the
installed plugin, or upload a release to the plugin registry.

See [the implementation plan](docs/development-plan.md),
[architecture](docs/decisions/001-repositories-and-engines.md), and
[contribution guide](CONTRIBUTING.md).

## License and citation

GPL-2.0-or-later; see [LICENSE](LICENSE), [NOTICE](NOTICE.md), and
[source provenance](source-provenance.json). The separate R implementation retains
its own licensing. Cite the software version and record the algorithm profile and
parameters from `run.json`; see [CITATION.cff](CITATION.cff).
