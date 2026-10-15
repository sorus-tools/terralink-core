# Contributing

Use Python 3.11+, install `.[web,test]`, and run `python -m pytest -q`.
For browser changes use `npm ci` in `apps/web`, then `python tools/build_web.py`.
Commit the regenerated packaged web assets with the source change.

Algorithm/geometry/routing changes must preserve feasibility and pass the frozen
reference cases or explicitly introduce a reviewed method-profile change. Add a
reproducible input and expectation for substantive bugs. Never loosen a tolerance
simply to make a changed corridor pass. Record any new upstream extraction hashes
and attribution. Use immutable revisions in compatibility/release reports.

Report interface, version/profile, input CRS and units, normalized settings,
minimal redistributable data, expected behavior, and actual result. Keep private
landscape data, credentials, environment files, and runtime uploads out of issues.

QGIS and R have their own repositories. Native R compatibility is measured, not
inferred from naming or version labels. Preserve R's native default runtime.
