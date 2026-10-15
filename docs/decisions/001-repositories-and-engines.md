# Repository and engine boundaries

Status: accepted for the initial standalone implementation.

The flagship core repository contains Python, CLI, web application/service,
language-independent method contracts and reference fixtures. Existing QGIS and R
repositories retain their history and release systems. The company marketing site
is separate. Three TerraLink product repositories are sufficient initially.

Python, the CLI and the standalone web service call the same extracted active
algorithm. An experimental QGIS build bundles that same numerical source with
native QGIS geometry and the existing UI. Native R remains a separate
implementation, with measured compatibility and independently recorded versions.

The transitional `_engine` preserves upstream scoring and selection, including
time limits. Its geometry facade uses Shapely/PyProj in standalone execution;
I/O hooks use Rasterio/Pyogrio. No global fake `qgis` modules are inserted. An
isolation lock protects the inherited process-global project/random state for
embedded API calls; the web service launches each analysis in a subprocess.

This keeps a functioning baseline while internal modules are gradually separated.
It avoids simultaneously rewriting selection, changing graph libraries, changing
the HTTP framework, and requiring a new language runtime for existing R users.

This alpha does not automatically deploy over the existing SORUS hosted tool,
upload a new stable QGIS release, or assert native R equivalence everywhere.
