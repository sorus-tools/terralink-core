# Compatibility and release status

This alpha is a usable standalone extraction, not a stable replacement for every
TerraLink distribution. The source can be installed without QGIS and is exercised
through Python, CLI and HTTP routes. CI defines a cross-OS installation/test
matrix; a configured CI matrix is not itself proof that every job has passed.

The initial frozen suite has 16 cases: four strategies across plain vector,
vector gap barriers, sealed vector barriers, and raster input. It compares
selected network topology, budget, polygon geometry and specific PRE/POST metrics.
The geometry tolerance is 0.001 square metres of symmetric difference; numeric
absolute tolerance is 1e-7 with a small relative floating-point allowance. These
thresholds do not permit barrier crossings or budget violations, checked separately.

The experimental QGIS bundle runs the same extracted selection/numerical source
with native QGIS geometry and the existing interface. Building it does not change
the installed plugin or upload a registry release. The stable QGIS 1.8.3 project
and its existing compatibility declaration remain intact until a new release is
accepted.

Native R is supported as a separate product and implementation. A portable capture
script runs it without enabling the experimental QGIS bridge. Its report states
which cases agree and which differ; a different profile is not relabeled as the
Python implementation. Existing public R releases and modified local R source are
distinct baselines. Additional native R alignment remains required wherever the
published compatibility report records a difference.

The reusable browser source has been extracted into `apps/web`; the new service
uses the standalone engine. The existing SORUS deployment is not switched by this
repository. The new service currently uses local storage, rather than reproducing
the old Cloud Run/Google Cloud Storage deployment configuration.

Future work includes broader landscape fixtures, deeper internal module separation,
broader verified QGIS builds, native R difference resolution, cloud-storage adapters,
and production rollout. None is represented as already released merely because
its design appears in the development plan.
