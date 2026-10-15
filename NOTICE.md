# Source attribution and license

TerraLink core is distributed under GPL-2.0-or-later. Original TerraLink code is
by Benjamin Bishop / SORUS Consulting LLC. The numerical and selection code in
`src/terralink_core/_engine` was extracted from TerraLink QGIS 1.8.3, revision
`2cb4a568e8990d7834019ce9bdbdfb7f3ae893f4`. Per-file original and extracted hashes
are in `source-provenance.json`. Interface-specific I/O is supplied separately.

The geometry backend's ring-area operation order is adapted from
`QgsLineString::sumUpArea` in QGIS, copyright 2014 Marco Hugentobler and QGIS
contributors, GPL-2.0-or-later:
https://github.com/qgis/QGIS/blob/release-3_44/src/core/geometry/qgslinestring.cpp
This arithmetic matters because tiny area differences can affect candidate ties.

The browser interface and hero image were extracted from the existing SORUS
TerraLink application. Its source hashes and extraction changes are recorded in
`web-source-provenance.json`. The SORUS business site and private content are not
part of this repository. Leaflet and map tile services retain their respective
licenses/attribution and are external browser resources. OpenStreetMap tiles are
an optional basemap; they do not participate in corridor analysis.

The native R project remains separately maintained with its own license and
implementation. Including it in the project documentation does not relicense it
or certify numerical equivalence on every scenario.

Synthetic conformance fixtures in this repository were generated for this project;
they contain no third-party or client landscape data and are available under CC0-1.0.
