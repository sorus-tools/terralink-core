# TerraLink: repository and platform development plan

Prepared 15 October 2026. Status: proposed architecture and implementation backlog, grounded in inspection of the existing local QGIS, R, and website code and their public repositories. This document plans the work; it does not report an implemented standalone engine or a completed migration.

## 1. Recommended decision

Create **one new flagship repository, `sorus-tools/terralink-core`**, and retain the two existing product repositories:

| Repository | Responsibility | Decision |
|---|---|---|
| `sorus-tools/terralink-core` | Standalone Python engine and command line; shared algorithm specification, schemas, conformance fixtures, ecosystem documentation; TerraLink web interface and HTTP service | Create as the main development and discovery home for the broader TerraLink project |
| `sorus-tools/TerraLink` | QGIS plugin, QGIS geometry adapter, plugin packaging, QGIS-specific documentation and integration tests | Keep its name, URL, history, tags, and existing plugin identity |
| `sorus-tools/terralink-r` | Native R implementation, R objects and plotting, package documentation, CRAN packaging and checks | Keep independent and supported |
| Existing SORUS website project | Company website, TerraLink marketing page, links to installation routes and online tool | Keep separate; extract only reusable TerraLink application code into the new repo |

This means **three TerraLink product repositories, with only one new repository to create**. The existing company website remains a separate concern. Avoid creating additional repositories for fixtures, documentation, the command line, and the web service at this stage.

Use **TerraLink** as the public product name. `terralink-core` is a repository and package name, not a replacement brand. Explain at the top of its README that it is also the home for the overall project, its method, documentation, and online application.

Proposed public description:

> TerraLink is open-source software for ecological connectivity and habitat-corridor planning under spatial, restoration-area, and barrier constraints. Use it through QGIS, R, Python, the command line, or a web interface.

Publish that complete availability statement when the advertised routes are actually released. During development, label Python and the new engine as previews and identify which engine powers the online service.

### Why this structure

An all-in-one repository could work technically, including an R package in a subdirectory. My recommendation reflects the assets already in place: QGIS and R have existing distribution identities, different runtime dependencies, and separate release requirements. Keeping them avoids a disruptive move and preserves a normal R package at its repository root.

Keeping the Python engine and web application together makes engine/API changes reviewable in one pull request. Keeping the company site separate avoids publishing unrelated business material and tying algorithm maintenance to general website releases.

| Alternative | Advantage | Cost | Judgment |
|---|---|---|---|
| Put every implementation in one new monorepo | Atomic changes across all source trees | Moves two established projects; mixed release pipelines and licenses; still does not eliminate the independent R implementation | Viable, but migration cost outweighs the benefit now |
| One repo per interface plus separate engine, fixtures, and docs repos | Very isolated components | More coordination, dependency updates, and places for users to search | Too fragmented for the current project |
| Evolve the existing QGIS repo into the whole project | Preserves the shortest existing TerraLink URL | Changes the meaning and layout of an established plugin repo during a large engine refactor | Reasonable alternative, but less clean than adding one flagship repo |
| New flagship engine/web repo plus existing QGIS and R repos | Preserves established products; groups shared contracts and web work | Requires explicit compatibility and dependency management across repos | Recommended |

Repository naming is subject to an availability check when creation begins. GitHub capitalization does not make `terralink` a different repository from the existing `TerraLink`; do not try to create that as a parallel project.

## 2. What already exists

These findings describe the **local sources inspected on 15 October 2026**. They are not a verification of the deployed website or of every registry release.

### QGIS plugin

- Local source: `${QGIS_SOURCE}`.
- Public repository: [sorus-tools/TerraLink](https://github.com/sorus-tools/TerraLink).
- Local HEAD: `2cb4a568e8990d7834019ce9bdbdfb7f3ae893f4`; clean working tree when inspected; metadata version `1.8.3`.
- The [official QGIS listing](https://plugins.qgis.org/plugins/TerraLink/) identifies `1.8.3` as the latest stable plugin, with QGIS `3.22`–`3.99` in that release's declared compatibility range. Do not extend that support claim merely because the code has Qt migration changes.
- `analysis_vector.py` has 21,593 lines and contains corridor analysis alongside QGIS geometry, file export, styling, and project operations.
- `graph_math.py`, `terralink_graph.py`, `terralink_engine.py`, `core_types.py`, `core_select.py`, and `landscape_metrics.py` provide reusable starting points. Their lack of direct QGIS imports does not establish that all four active selection paths are already separated. In particular, inspect call sites before treating `core_select.py` as the active shared selector.
- Raster analysis polygonizes habitat and delegates to the vector corridor backend.
- The Processing provider currently opens the dialog. It is not yet a fully parameterized batch-analysis algorithm.
- Metadata declares `GPL-2.0-or-later`; the local license file contains an abbreviated license text.

### R package

- Local source: `${R_SOURCE}`.
- Public repository: [sorus-tools/terralink-r](https://github.com/sorus-tools/terralink-r).
- Local HEAD: `40150e6f99f2ea61cf303cab628f54d4e70a1156`; the working tree contains numerous modified and untracked files. The local `DESCRIPTION` says `1.8.2`; the last release commit shown locally is `1.7.0`. The public README also describes an older strategy surface. These are distinct baselines, not interchangeable versions.
- About 12,755 lines across the local `R/` files; this is a substantial native implementation, using `sf`, `terra`, `igraph`, and related packages.
- Native R is the normal route. An experimental raster QGIS bridge is gated by `TERRALINK_EXPERIMENTAL_QGIS_RASTER_BRIDGE=1` and contains Mac-specific discovery paths. It should not become a dependency of the default R workflow.
- Existing testthat tests and synthetic parity data are useful starting points. Some obstacle tests skip when optional routing dependencies are absent; a skipped test is not evidence that the routing feature passes.
- Existing parity helper scripts contain local absolute paths and some cover only three strategies. Generalize them and include all four current modes.
- Local package metadata declares `MIT + file LICENSE`. Do not assume that this resolves provenance or licensing for any cross-language ports; audit actual sources before moving code between licensing boundaries.
- Current CRAN release details were not established during this inspection. Verify registry metadata and checks during the baseline phase before making migration claims about CRAN.

### Browser and server

- Local project: `${WEBSITE_SOURCE}`.
- Interface: `src/pages/tools/terralink-online.astro`.
- Service: `services/terralink-runner/app.py` and `terralink_runner.py`.
- This is a browser interface to a **server-side QGIS analysis process**, not a separate JavaScript implementation of the corridor algorithm.
- The Flask service exposes `/healthz`, `/preview`, and synchronous `/run` routes. It returns output downloads, GeoJSON previews, statistics, logs, and preview warnings. Cloud Run and Google Cloud Storage are existing deployment integrations; local operation is also represented in the code.
- A copied `terralink_plugin/` directory supplies the algorithm. Several important files differ from the standalone QGIS repo; differences were detected, but their full behavioral effects were not evaluated here.
- Runner documentation identifies a `1.8.2` engine. Its documented 300-second default timeout differs from the current code's 600-second fallback; deployment configuration may override either. Resolve the effective value from the actual deployment before documenting it as current production behavior.
- The website working tree contains extensive untracked content, including the online interface and runner. The inspected Git checkout tracks none of those application paths. A clone of that commit would not reproduce this local application.
- Existing company content, environment files, backups, uploads, logs, and local outputs must not be imported wholesale into a public repo.

### Consequence for the design

The initial goal is **one authoritative method specification, one shared Python engine for standalone Python/QGIS/web, and one supported native R implementation checked against that specification**.

That is two maintained algorithm implementations while native R remains independent. It is not honest to promise a single executable implementation across every interface without either requiring Python in R or undertaking a shared compiled-engine project. Both would add substantial work and installation implications. Revisit a compiled common core only if measured maintenance or performance needs justify it later.

## 3. How the components fit together

```text
                    TerraLink method and compatibility specification
                    Shared schemas, fixtures, expected results
                         /                         \
             Python reference engine          Native R implementation
                 /       |       \                |
             Python     CLI     HTTP service   R package / RStudio
                                  |
                              Web interface

             Python reference engine
                      |
             QGIS adapter and interface
```

The QGIS adapter may initially retain QGIS geometry operations while sharing the extracted numerical/selection logic. The standalone engine uses a QGIS-free geometry implementation. Both must satisfy the same operation and conformance tests. Shared selection code alone does not guarantee equal corridor geometry or candidate sets.

The browser uploads files, submits settings, and renders results. The HTTP service manages requests, storage, execution, and previews. The engine performs analysis. This separation lets a self-hosted service and the SORUS-hosted service use the same engine without embedding cloud account settings in the algorithm.

Full offline computation inside the browser, through WebAssembly or an in-browser Python runtime, is a possible future project. It is not required for the proposed web version and should not delay this migration.

## 4. What belongs in the new repository

Proposed layout, to be implemented incrementally rather than by creating empty placeholder modules:

```text
terralink-core/
  README.md
  LICENSE
  NOTICE.md
  CITATION.cff
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  AGENTS.md
  pyproject.toml
  src/terralink_core/
    api.py
    models.py
    validation.py
    units.py
    pipeline.py
    optimization/
    graph/
    routing/
    metrics/
    geometry/              # narrow operation contracts and standalone backend
    io/                    # vector/raster files, manifests, result writers
    cli.py
  services/http/           # Flask service first; avoid simultaneous framework rewrite
  apps/web/                # extracted TerraLink tool, styles, sample-data flow
  spec/
    algorithm.md
    parameters.md
    strategies.md
    metrics.md
    compatibility.md
    schemas/
  conformance/
    fixtures/
    expected/
    runners/
    tolerances.yaml
    known-differences.yaml
  tests/
    unit/
    integration/
    regression/
  benchmarks/
  examples/
    python/
    cli/
    notebooks/
  docs/
    getting-started/
    methods/
    integrations/
    development/
    deployment/
    decisions/
  tools/                   # build, fixture export, compatibility report utilities
  .github/workflows/
```

Keep QGIS UI source and native R source in their existing repos. The flagship repo links to them and runs cross-project compatibility checks against pinned revisions. It should not keep manually edited mirrors of their complete source trees.

Published artifacts should eventually include a Python wheel/source distribution, an offline conformance bundle, documentation, and optional self-hosting deployment artifacts. The QGIS ZIP and R source package remain outputs of their own repositories.

## 5. Shared method, parameters, and results

Before porting code, write down exactly what has to stay equivalent.

### Stable strategy identifiers

Preserve the current machine identifiers and document display labels separately:

| Machine identifier | Current public label | Intended objective to specify and test |
|---|---|---|
| `most_connected_networks_2` | Most Connected Networks A | Component-pair value and valuable joins involving existing networks |
| `most_connected_networks` | Most Connected Networks B | Habitat area recruited into connected networks |
| `largest_single_network` | Largest Single Network | One dominant connected network |
| `landscape_fluidity` | Landscape Fluidity | Graph-based movement efficiency and redundancy |

Audit actual scoring formulas, candidate caps, rescue/refill rules, tie-breaks, and final export filters in each version. Those details belong in the method profile, not just prose summaries. Older R names require a documented version-aware mapping; do not silently reinterpret historical settings as different algorithms.

### Units and spatial behavior

- Normalize internal distances to metres and areas to square metres, with named conversion boundaries. Preserve hectares/acres/cell-count input behavior through explicit adapters and regression checks.
- A corridor area budget remains an area budget. Do not market it as monetary cost optimization unless a separately specified cost model is implemented.
- Record source CRS, analysis CRS, output CRS, and any reprojection. Use a suitable projected analysis CRS; reject or explicitly resolve unsuitable inputs instead of measuring degrees as metres. Document limitations for large extents and projection distortion.
- Specify how geographic inputs select an analysis CRS; do not assume a single UTM zone is suitable for every landscape.
- Specify raster band selection, class/range inclusion, NoData behavior, 4/8 connectivity, origin, transform, pixel area, resampling, and rasterization. Non-square or rotated cells need an explicit rule or a clear unsupported-case error.
- Specify whether budget accounting uses summed corridor areas, incremental new habitat, unioned geometry, or another existing rule. Measure and preserve the chosen baseline; do not change it accidentally during unit normalization.
- Fix buffer segment conventions, precision, validity repair, multipart treatment, zero-distance joins, and barrier-touch/overlap rules. Buffer and union differences can change costs and selected links.
- Record routing resolution, corridor width, bottleneck handling, simplification/smoothing, and all candidate admission stages. Validate the final buffered corridor against barriers, not only its centerline.

### Common run contract

Define versioned request, result, capabilities, and error schemas. Accept structured values rather than ambiguous dictionaries internally. A request includes input references/layer names, mode, strategy, units, budget, corridor width, search distance, filtering, barriers, routing settings, metric settings, and computation limits.

Each result should include:

- Selected corridors, patch/network identifiers, and connected networks.
- PRE/POST metrics with definitions, units, and exact/approximate status.
- Candidate and rejection counts, budget accounting, warnings, and stop reasons.
- Normalized parameters plus original supplied units and defaults used.
- Implementation ID (`python`, `qgis-adapter`, or `r-native`), implementation version, algorithm profile, schema version, backend/dependency versions, and source revision.
- Input content hashes, analysis CRS/grid metadata, random seed or sampling settings, and any time/work limits reached.
- An output manifest with files, layer names, field meanings, CRS, and optional artifact hashes.

Keep display geometry and simplified web previews separate from analytical output. A preview failure must not erase an otherwise successful analysis.

Distinguish package version, algorithm profile, and schema version. A QGIS packaging-only patch should not imply a different corridor method. Likewise, matching version numbers do not prove the R and Python implementations agree.

### File interoperability and entry points

Make GeoPackage and GeoJSON the first-class vector file inputs and GeoTIFF the first-class raster input. Preserve the existing web routes for zipped shapefiles and KML through input adapters, testing driver availability and multilayer selection explicitly. An advertised file format must work in the distributed artifact, not just on the development Mac. Accept in-memory objects through optional Python/R convenience adapters without requiring their data-frame libraries in the numerical layer.

Use GeoPackage for the canonical corridor and connected-network geometry bundle, CSV for tabular summaries, JSON for machine-readable settings/metrics/provenance, and a readable text report. Offer GeoTIFF corridor/network display products for raster workflows. Preserve existing output field names and return shapes through versioned interface adapters, or document a migration when a field changes. Keep full-resolution analytical output independent of any web display simplification.

The intended command-line experience is a file-based run such as `terralink run --config scenario.json --output results/`; that is a proposed interface, not an available command today. A Python user calls the same pipeline with a typed configuration. Both routes should produce equivalent normalized settings and results. Configuration examples must state units, input layer/band, CRS policy, algorithm profile, and computation limits so that they can be reused unambiguously.

Standard file outputs also let ArcGIS and other GIS users inspect and reuse TerraLink results without adding a dedicated integration immediately. An ArcGIS toolbox is a later adapter project with its own runtime tests; this plan does not claim that such an integration already exists.

## 6. Engine and dependency approach

### Extract in layers

1. Recover the actual active pipeline and identify the numerical, geometry, I/O, and interface boundaries.
2. Extract shared data models, graph operations, strategy scoring/selection, accounting, and metrics while the QGIS implementation still runs.
3. Define the smallest geometry/raster operation interface needed by the active code. Avoid building a general GIS framework.
4. Implement and compare a QGIS adapter and a standalone backend for those operations.
5. Move orchestration and file-based analysis behind a stable Python API and command line.

Retain the existing graph compatibility code initially. Replacing it with NetworkX or rewriting the optimizer at the same time would introduce another behavior change to diagnose.

### Dependencies

Use standard-library Python and NumPy for the shared numerical layer where practical. Keep QGIS, Qt, Flask, browser tooling, and cloud libraries outside that layer. For standalone geometry and raster I/O, prototype Shapely, PyProj, Rasterio, and a vector file reader/writer such as Pyogrio; use GeoPandas as an optional convenience rather than requiring it everywhere. Final versions and minimum Python support must follow clean installation and compatibility tests.

[Shapely](https://shapely.readthedocs.io/en/stable/) provides planar geometry operations, and [Rasterio](https://rasterio.readthedocs.io/en/stable/) provides geospatial raster access. They are proposed building blocks, not evidence that QGIS behavior will be reproduced automatically.

Provide dependency groups so a graph-only user does not need the HTTP server or raster stack. Proposed distribution name: `terralink-core`; proposed import: `terralink_core`; proposed command: `terralink`. Verify registry availability before publishing. Follow the [Python packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/) for build metadata and distribution layout.

### QGIS installation constraint

Normal plugin installation should remain a single QGIS plugin installation, without terminal package installation or an online download at first run. Build the required pure-Python core into a private plugin namespace from an exact released artifact or commit, preserving license notices and recording its checksum. Generated bundled source is not hand-edited.

Use QGIS's existing geometry/raster facilities through the adapter where this avoids native-library installation conflicts. If the extraction discovers an unavoidable third-party binary dependency, resolve distribution on the supported QGIS/OS combinations before switching the plugin. Do not assume pip packages can be safely injected into every QGIS environment.

Keep the plugin directory/class factory and existing identities stable; the repository layout and [QGIS plugin structure](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/plugins/plugins.html) are different concerns.

## 7. R: preserve independence and make compatibility measurable

Continue supporting `terralink_raster()`, `terralink_vector()`, `sf` corridor/network objects, `terra` rasters, plotting, and R-native errors/progress. Do not make Python, QGIS, a server, an account, or an internet connection a default requirement.

The new flagship repo supplies the method specification, parameter semantics, and conformance bundle. R consumes a pinned offline bundle in tests. Copy tiny fixture files into an R test/package location through a documented import script that records source version and hashes. Avoid network fetches during package installation, examples, or checks. Maintain R package organization and checks in line with [Writing R Extensions](https://cran.r-project.org/doc/manuals/r-release/R-exts.html).

For every mode, publish whether R has exact fixture agreement, agreement within defined geometry/numerical tolerances, or an explicitly documented implementation difference. Do not label broad qualitative similarity as parity. Fix incompatibilities or identify unsupported options clearly; require the same feasibility rules even when optimizer tie outcomes differ.

An optional Python-backed R route could be considered later for users who explicitly want that implementation. It must be an explicit backend choice, with recorded provenance; it must never silently replace native R depending on what is installed on a computer. The current experimental QGIS bridge should be isolated from default checks and clearly labeled during the migration.

## 8. Browser: keep the interface, replace the engine behind it

Preserve the useful existing flow: upload habitat and barriers, choose raster/vector settings and objective, preview, run, inspect the map and metrics, download outputs.

Extract only the TerraLink tool and its necessary assets from the company site. Identify dependencies on shared layouts, styles, map libraries, and subscriptions before copying; keep the company marketing/subscription logic in the website where possible. Publish the reusable tool without hard-coded SORUS cloud resources. The existing online URL should continue to work through an integration or redirect that preserves the user journey.

Migration sequence:

1. Reproduce the current local UI/service from an allowlisted source export and record the exact vendored engine baseline.
2. Test the existing `/preview` and `/run` response shapes and download behavior before changing them.
3. Add a server-side adapter that translates existing web parameters into the new run contract.
4. Switch a staging service to the standalone engine once it passes the required raster/vector and barrier fixtures. Exercise actual uploads and downloads, not just direct function calls.
5. Compare staging outputs with frozen legacy outputs. Show the implementation/profile/version in downloadable run metadata.
6. Switch production only after acceptance; retain the previous service artifact and a documented routing/configuration rollback.
7. Retire the copied QGIS plugin and QGIS/Qt server runtime after the new route is accepted.

Keep Flask for the first migration. Keep the synchronous API for small jobs initially. If measured workloads require longer jobs, add an optional versioned job API with states, progress, cancellation, expiry, and download retrieval; keep the legacy endpoint during a documented transition. A queue/database should be introduced for an observed execution need, not as a prerequisite for extracting the engine.

Retain configurable upload limits, execution limits, per-client throttling, and worker concurrency. Validate archive paths, expanded size/file count, supported formats/layers, and file references. Public processing should run in an isolated worker process with bounded resources and no need for client access to server filesystem paths or arbitrary remote data URLs. Specify upload/output retention and access policy for hosted analyses and clean temporary files reliably. These checks belong at the service boundary, not in every optimizer function.

Support local filesystem storage and a replaceable cloud-storage adapter. Self-hosting should not require a SORUS account. The SORUS website's existing instructions use direct local processes; retain that local workflow during extraction. Existing container-based production deployment can remain an option, without making Docker a new local-development requirement.

## 9. Conformance and scientific QA

### Freeze baselines before refactoring

Capture released QGIS `1.8.3`, the chosen native R working snapshot and released R baseline, and the chosen web runner snapshot separately. Record source revisions and dirty-file hashes. Compare each against the same inputs and settings. Current agreement is a question to measure, not a premise.

The reference for intended 1.8 behavior starts with QGIS `1.8.3` plus the explicit method specification. If a known bug is identified, add an independently justified expectation and document a method/profile change. Do not preserve a defect merely to match a golden output, and do not silently change outputs under an unchanged profile.

### Required fixture families

| Family | What it establishes |
|---|---|
| Tiny hand-checkable graphs | Strategy scoring, tie-breaking, budget decisions, exact expected network membership |
| Simple polygon patches | Candidate formation, width/area accounting, connection geometry |
| Raster patches | Polygonization, 4/8 connectivity, NoData, pixel-unit behavior, raster display output |
| Complete barrier and barrier with a gap | No crossing through a sealed barrier; feasible width-aware detour through a genuine gap |
| Narrow passage and smoothing case | Final corridor remains feasible after buffering, clipping, and smoothing |
| A–B–C stepping stones | Multi-link chain handling and intermediate patches |
| Loops and parallel routes | MCN-A/MCN-B distinction, LSN consolidation, LF redundancy behavior |
| Budget and degenerate inputs | Exact-budget boundaries, zero/no feasible links, empty/filtered habitat, already touching patches |
| Units, CRS, and grid cases | Metric/imperial equivalence after normalization; projected/geographic handling; non-square-cell policy |
| Invalid/multipart geometries | Explicit repair/skip behavior and reproducible diagnostics |
| Candidate/time limits | Honest early-stop reporting and deterministic work-bounded reference runs |
| Representative larger landscape | Practical runtime/memory and unexpected quality changes |

Exercise every applicable mode for both raster and vector routes. Parameterize the fixtures rather than maintaining unrelated hand-copied tests per platform. Existing R synthetic datasets and prior runner artifacts can seed the suite after data licensing and expected results are checked.

### Comparison rules

- On identical supplied candidate graphs, require the specified selected edges, objective, budget, and tie behavior for deterministic hand-checkable cases.
- On controlled end-to-end fixtures, compare patch membership, selected network topology, costs, PRE/POST metrics, and final geometry. Canonicalize IDs/geometry ordering before comparing.
- Store metric-specific absolute/relative tolerances and geometry precision rules in the fixture manifest before assessing the new implementation. Choose tolerances from scale, precision, and baseline repeatability; avoid an arbitrary global percentage.
- Geometry tolerances must not excuse a corridor crossing an impassable barrier or overspending the defined budget. Feasibility violations fail separately.
- Permit different equal-value solutions only where the fixture explicitly defines that equivalence, including geometry and feasibility conditions. Do not hide missing links behind a similar aggregate metric.
- Separate deterministic operation/candidate-bounded regression runs from time-limited production runs. A fixed random seed cannot make wall-clock-limited searches identical across machines. Report truncation and make reproducibility claims conditional on mode and limits.
- Engine extraction may use frozen outputs as regression evidence; ecological validity requires independent scientific reasoning and, where available, observations. Agreement between R and Python is implementation evidence, not validation of animal movement predictions.

### CI and release gates

Run fast shared-core and schema tests on pull requests. Run standalone vector/raster integration and conformance tests with all required routing dependencies installed. Add clean Windows, macOS, and Linux installation/sample-run coverage for the standalone package; select supported Python/NumPy ranges based on the tested matrix. Add QGIS integration and ZIP-install checks on explicitly selected supported builds; check Qt/QGIS generations separately before claiming new support. Expand R checks beyond the existing Linux workflow, including a job that actually executes optional obstacle routing tests.

Cross-repo tests use immutable source revisions and a pinned conformance bundle. Do not test releases against three moving default branches. Run a scheduled development compatibility check separately, and keep its findings distinct from release certification.

## 10. Implementation phases and acceptance gates

Durations below are rough planning allowances for focused development, not delivery promises. Re-estimate after the baseline and standalone geometry spike. Expect the geometry/routing extraction and genuine R alignment to dominate effort.

| Phase | Indicative effort | Deliverables | Exit condition |
|---|---:|---|---|
| 0. Protect and inventory current work | 2–4 days | Snapshot manifest; allowlisted source exports; version/feature/license inventory; deployment facts | Each selected source can be reproduced without overwriting local work or importing private/runtime files |
| 1. Specify and establish baselines | 3–5 days | Method profile, schemas, fixtures, cross-version comparison, documented differences | All four modes captured; acceptance rules written; current disagreements visible |
| 2. Create flagship scaffold and extraction spike | 3–5 days | New repo foundation, package skeleton, one complete standalone vector case, geometry backend decision | A useful end-to-end run completes with no QGIS installed; dependency/packaging feasibility established |
| 3. Extract the full standalone engine | 10–18 days | Shared active selectors/metrics, routing, vector/raster pipelines, API, CLI, result writers | Four modes and required barrier cases pass; provenance and computation limits recorded |
| 4. Integrate QGIS and align R | 7–12 days | Reproducible plugin bundle and adapter; native R fixture integration and fixes; compatibility report | Plugin installs normally; R runs natively; required conformance gates pass or capabilities are explicitly narrowed |
| 5. Migrate the browser service and tool | 4–7 days | Extracted web app/service, API compatibility, standalone staging, storage configuration, rollback runbook | Real upload/preview/run/download scenarios pass and accepted results agree with the selected profile |
| 6. Package and launch | 3–5 days | Release candidates, clean-install checks, docs, examples, citation, release matrix | Advertised interfaces meet the final definition of done and rollback artifacts exist |

Total initial allowance: approximately **32–56 focused developer days**, plus external registry/review time. This is deliberately broader than a cosmetic repository move. Stop and re-estimate if Phase 2 exposes extensive geometry divergence or Phase 1 finds deep R method differences.

### Phase 0: concrete work

- Enumerate local source, remote refs/tags, registry versions, deployed web artifact/configuration, installed QGIS plugin, and fixture datasets. Record each separately.
- Preserve modified/untracked R and website source in a controlled snapshot before any migrations. Do not stage the entire website or run destructive Git cleanup. Collect private config names for documentation without including their values in public exports.
- Compare the runner copy with QGIS source at function level; classify differences as algorithm, I/O, runtime, and display.
- Inventory licenses and data provenance. Retain existing notices on extracted code; use the inherited GPL terms for QGIS-derived core code unless a rights review establishes a different option. Keep the R license declaration unchanged until provenance is understood. Supply complete license texts in distributed artifacts.
- Verify proposed repository/package names. Establish Python/QGIS/R and operating-system compatibility targets from actual environments and clean-test feasibility.
- Import extracted source with its original revision, path mapping, copyright notices, and a documented provenance manifest. Preserve existing repository history in place; use a history-preserving subset import where useful rather than rewriting the plugin or R repository.

### Phase 1: concrete work

- Write scoring/accounting rules for each mode and map current parameter/default differences. Resolve MCN label/history mappings explicitly.
- Build portable fixture runners from the existing R/QGIS parity helpers; remove hard-coded personal paths. Include both MCN modes.
- Run the selected baselines multiple times where timing/sampling matters. Save normalized outputs, exact inputs, work limits, dependency versions, and expected differences.
- Publish a baseline report internally before changing the engine. Establish the algorithm profile and tolerance rules.

### Phases 2–3: concrete work

- Initialize the new repo with source provenance, build metadata, a short architecture decision, contributor instructions, and CI. Keep the initial core prerelease separate from plugin/R version numbers.
- Trace calls from `run_vector_analysis()` and `run_raster_analysis()`; move only active logic in small reviewable slices. Avoid copying the 21,593-line module intact and calling it a finished library.
- Build a thin geometry operation prototype around a simple corridor, an obstacle detour, a union/accounting case, and raster polygonization. Compare QGIS and standalone semantics before committing to dependency versions.
- Extract scoring/selection/accounting and metrics with regression coverage at each boundary. Introduce progress/cancellation callbacks and structured errors without importing interface libraries into the engine.
- Add file-based API and command line, vector/raster I/O, validators, manifests, and optional raster display exports. Preserve existing selection strategy; version any deliberate change separately.

### Phase 4: concrete work

- In the QGIS repo, create the adapter around live layers, CRS, project integration, and styling. Bundle the core from a pinned source artifact into a private namespace.
- Keep current plugin install/launch behavior and identifiers stable. A fully parameterized Processing analysis tool is a useful later enhancement; it is not a reason to delay basic migration.
- In the R repo, preserve API/object behavior, add versioned contract translation and offline conformance data, then fix measured method gaps with explicit release notes.
- Keep different implementation versions visible. A large unresolved mode divergence requires either more alignment work or a clearly narrower advertised compatibility profile.

### Phases 5–6: concrete work

- Extract the tool and service through an allowlist. Keep the marketing page and business-specific features in the SORUS project.
- Preserve web request compatibility through an adapter; stage the standalone engine and verify output files/previews through HTTP.
- Produce release candidates and immutable artifact manifests. Package Python first, build the plugin against that exact artifact, certify the R version against the conformance profile, and pin the web service to the certified Python engine.
- Publish ecosystem docs, the interface/version matrix, and examples. Preserve prior artifacts and make rollback a tested configuration/artifact switch.

## 11. Ordered backlog for implementation

Each row is intended to become one issue or a small group of pull requests. Effort may be split after the baseline report. Dependencies are logical gates, not instructions to introduce a multi-agent workflow.

| ID | Work item | Depends on | Acceptance evidence |
|---|---|---|---|
| TL-01 | Reproducible snapshot and source inventory | — | Manifest identifies clean/dirty snapshots, hashes, versions, source locations, and excluded private/runtime material |
| TL-02 | Compare QGIS/R/runner behavior and licenses | TL-01 | Four-mode/default/output/provenance table and categorized diff report |
| TL-03 | Method and parameter contract | TL-02 | Scoring, units, budget, CRS, masks, limits, and historic strategy aliases specified |
| TL-04 | Portable fixtures and baseline runners | TL-01, TL-03 | All required fixture families represented; baseline outputs and known differences captured |
| TL-05 | New flagship repository and package foundation | TL-01, TL-02 | Clean checkout builds/imports the initial package; notices and contribution instructions present |
| TL-06 | Standalone geometry/raster spike | TL-03, TL-04, TL-05 | Non-QGIS simple corridor, detour, union, and polygonization comparisons; supported dependency plan |
| TL-07 | Extract active graph and selection logic | TL-04, TL-05 | Graph-level scoring/tie/budget tests pass; actual pipeline invokes the extracted code |
| TL-08 | Extract shared metrics and diagnostics | TL-04, TL-07 | PRE/POST reference metrics, sample settings, and approximation labels checked |
| TL-09 | Complete standalone vector and routing pipeline | TL-06, TL-07, TL-08 | Four-mode vector conformance, final-width barrier checks, accounting, and stop reasons pass |
| TL-10 | Complete raster preprocessing and exports | TL-06, TL-09 | Class/range/NoData/connectivity/unit fixtures pass; canonical vector and optional raster outputs documented |
| TL-11 | Public Python API, CLI, and manifest writer | TL-09, TL-10 | Same settings through API/CLI give equivalent normalized results; installable artifacts |
| TL-12 | Clean-install and cross-OS release checks | TL-11 | Supported environments install from built artifacts and run sample vector/raster jobs without QGIS |
| TL-13 | QGIS adapter and reproducible bundling | TL-07, TL-08, TL-11 | ZIP installs on selected QGIS builds; bundled core identity/hash recorded; representative parity tests pass |
| TL-14 | R conformance integration and native alignment | TL-03, TL-04; final comparison after TL-09/10 | Native R runs offline; all four modes tested; optional routing tests executed; differences resolved/documented |
| TL-15 | Extract reusable online tool and server | TL-01, TL-05 | Local clean checkout serves the tool with configurable API/storage and no company-private files |
| TL-16 | Web contract adapter and standalone staging | TL-11, TL-15 | Upload/preview/run/download tests pass; manifests identify engine/profile; current response compatibility |
| TL-17 | Web rollout and rollback | TL-12, TL-16 | Accepted staging comparison; pinned production artifact; tested rollback and retention behavior |
| TL-18 | Ecosystem docs, methods, citation, examples | TL-03, TL-11, TL-13, TL-14, TL-16 | One discovery page accurately routes each audience; executable examples and support matrix |
| TL-19 | Coordinated stable release | TL-12, TL-13, TL-14, TL-17, TL-18 | Signed-off release matrix, published artifacts/checksums, accepted conformance report, registry checks |
| TL-20 | Later enhancements | Stable release | Prioritize from actual use: batch Processing tool, async jobs, further formats, compiled hotspots, browser-local experiments |

Suggested commit/PR sequence for the first implementation milestone: snapshot/inventory; contract and fixtures; package foundation; one standalone vertical slice. Keep new optimization features out of those PRs.

## 12. Distribution, versioning, and maintenance

- Start the new Python engine with prereleases such as `0.1.0a1`; do not relabel the plugin `1.8.3` as if it were already a standalone release. Declare the covered algorithm profile explicitly. A stable `1.0` requires the supported standalone surface to pass its acceptance gates.
- Keep independent implementation versions. Publish a release matrix that maps core version, QGIS plugin version, R package version, web build, schema version, algorithm profile, and conformance bundle hash.
- No hand-maintained engine copies in the web runner. The service depends on an exact released core artifact. The plugin's bundled core is generated, pinned, and checked against source.
- Use one canonical method/specification and fixture source. Contract updates accompany relevant code changes; deliberate behavior changes require a recorded decision and updated expected results.
- Use issue templates that collect interface, implementation/profile version, input type, units, CRS, normalized settings, and minimal reproducible data. General method questions belong in the flagship repo; QGIS/R-specific faults can remain in their repositories.
- Build documentation and examples from released artifacts where practical. Keep the flagship status matrix honest about preview features, tested operating systems, unsupported options, and implementation differences.
- Keep release assets out of normal source history where practical; retain historical ZIPs already in the QGIS repo without rewriting history just to clean them up.
- Retain contributor attribution and source provenance. Publish a software citation and version information; a future software/method paper should describe the actual objectives and heuristics and distinguish software verification from ecological validation.

## 13. Inclusive user experience and public positioning

The main landing page and flagship README should lead with what TerraLink does, then offer equally clear routes:

| User | Recommended route | Inclusion requirement |
|---|---|---|
| GIS practitioner | QGIS plugin | Normal plugin installation, local files, offline analysis, familiar map outputs |
| R researcher | Native R package | Existing R functions and objects; no required Python/GIS installation or account |
| Python researcher/developer | Python package | Installable package, API reference, notebooks, provenance and batch examples |
| Workflow/server user | Command line | File/config inputs, machine-readable errors/results, stable exit behavior |
| First-time user | Online tool with a supplied example | No coding needed; explicit workload limits, accessible forms, clear download flow |
| Organization/developer | Self-hosted web service | Configurable storage/runtime; documented API; no SORUS-only dependency |

Use readable mode descriptions alongside stable machine identifiers. Support keyboard use, labeled fields, understandable errors, and a downloadable settings/metrics record that does not rely on color interpretation. Supply a small redistributable example dataset so users can try the tool without preparing habitat layers first.

Keep the QGIS entry prominent for the current audience while advertising TerraLink as the broader software project. The browser is an access route and demonstration/hosted workflow; R and Python provide research/programmatic routes. The hosted web workload limit should direct larger jobs to the appropriate local option without implying the web service and local engine have different ecological objectives.

Do not claim universal optimality or organism movement truth. Document heuristic and candidate/time-limit behavior, explain that Landscape Fluidity is graph-based rather than a full landscape current-flow solver, and encourage comparison of plausible scenarios.

## 14. Definition of done

The initial repository-and-engine project is complete when:

1. The new public flagship has a clear purpose, source provenance, complete licenses, method specification, support matrix, examples, and contribution instructions.
2. A fresh supported machine can install the standalone package and run supported raster/vector analyses through Python and the command line **without QGIS**.
3. All four current modes, area-budget semantics, routing/barriers, units, PRE/POST metrics, and declared outputs pass the agreed fixture gates.
4. The QGIS plugin installs normally and uses a reproducibly bundled core plus a tested adapter, without manual dependency installation for the supported route.
5. Native R remains usable with its established public workflow and satisfies the advertised conformance profile. Any narrower capability is explicit and tested.
6. The extracted web tool works against the standalone service; hosted uploads, previews, results, downloads, limits, retention, and rollback are checked.
7. A compatibility report identifies exact versions/revisions and cannot be confused with a claim that every historical release produces identical results.
8. Users can discover QGIS, R, Python, command-line, and online options from one TerraLink home and understand which routes are stable.

The first actionable milestone is **the protected baseline plus one complete QGIS-free analysis**, not a simultaneous rewrite of all three existing products. That milestone will make the remaining effort and compatibility risks concrete.

## 15. Evidence and limits of this plan

The architecture recommendation is a judgment based on the inspected source structure and existing distribution channels. It is not a claim that multi-repo development is universally preferable.

Local evidence used: QGIS metadata/README/engine/Processing files; R DESCRIPTION/README/NEWS/native analysis and tests/parity scripts; runner README, Flask routes, QGIS initializer, vendored engine comparisons; Astro form and fetch paths; Git revision/status/tracked-path inventories. No analysis jobs, package checks, live QGIS operations, or production deployment tests were run for this planning request. Source trees were read, not changed.

Public primary references checked:

- [TerraLink QGIS source](https://github.com/sorus-tools/TerraLink) and [official plugin listing](https://plugins.qgis.org/plugins/TerraLink/) for the established QGIS project and distribution identity.
- [TerraLink R source](https://github.com/sorus-tools/terralink-r) for the established separate R project. Its public snapshot must be distinguished from modified local source.
- [Python packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/) for the proposed standalone package/build structure.
- [QGIS plugin structure](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/plugins/plugins.html) for the separate plugin entrypoint/metadata concerns.
- [Writing R Extensions](https://cran.r-project.org/doc/manuals/r-release/R-exts.html) for native R package structure and build/check considerations.
- [Shapely](https://shapely.readthedocs.io/en/stable/) and [Rasterio](https://rasterio.readthedocs.io/en/stable/) as candidate standalone geometry and raster building blocks.

Exact registry/deployment state, package-name availability, license provenance across prior ports, and actual numerical parity remain Phase 0/1 verification tasks. They do not prevent selecting the architecture, but they must be resolved before release claims or broad source migration.
