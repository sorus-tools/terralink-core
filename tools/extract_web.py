"""One-time allowlisted extraction of the existing TerraLink tool.

Source ownership remains with the TerraLink/SORUS project. No company configs,
private content, subscription credentials, or runtime artifacts are copied.
"""

from pathlib import Path
import hashlib
import json


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("website", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / "apps/web"
    sources = {
        "src/pages/tools/terralink-online.astro": "src/pages/tools/terralink-online.astro",
        "src/styles/global.css": "src/styles/global.css",
        "src/assets/terralink-hero.png": "src/assets/terralink-hero.png",
    }
    records = {}
    for source, destination in sources.items():
        content = (args.website / source).read_bytes()
        out = target / destination
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(content)
        records[source] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "destination": str(out.relative_to(root)),
        }
    page = target / "src/pages/tools/terralink-online.astro"
    text = page.read_text()
    text = text.replace(
        'import.meta.env.PUBLIC_TERRALINK_RUNNER_URL || ""',
        'import.meta.env.PUBLIC_TERRALINK_RUNNER_URL || "/api"',
    )
    text = text.replace(
        'const apiBase = (runnerUrl || "").replace(/\\/$/, "");',
        'const apiBase = (runnerUrl || "").replace(/\\/$/, "");\n  const escapeHtml = (value) => String(value).replace(/[&<>"\']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;","\'":"&#39;"}[c]));',
    )
    text = text.replace(
        "return key\n      .replace", "return escapeHtml(key)\n      .replace"
    )
    text = text.replace("return String(value);", "return escapeHtml(value);")
    text = text.replace(
        "const buttondownUsername = import.meta.env.PUBLIC_BUTTONDOWN_USERNAME?.trim();",
        'const buttondownUsername = "";',
    )
    text = text.replace(
        'href="/terralink"', 'href="https://github.com/sorus-tools/terralink-core"'
    )
    text = text.replace(
        "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    )
    text = text.replace(
        'attribution: "&copy; Google"',
        "attribution: '&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors'",
    )
    text = text.replace(
        'subdomains: ["mt0", "mt1", "mt2", "mt3"],', 'subdomains: ["a", "b", "c"],'
    )
    # Uploaded names can flow into API output labels. Escape HTML before inserting them.
    text = text.replace(
        'const safeLabel = output.label || output.filename || "Output";',
        'const escapeHtml = (v) => String(v).replace(/[&<>"\']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;", "\'":"&#39;"}[c]));\n        const safeLabel = escapeHtml(output.label || output.filename || "Output");',
    )
    text = text.replace(
        "TERRALINK ONLINE VERSION V1.8.2", "TERRALINK STANDALONE ENGINE PREVIEW 0.1.0a1"
    )
    text = text.replace('step="0.1"', 'step="any"')
    text = text.replace(
        "The R package is available on", "Use the native R package through its"
    )
    text = text.replace(
        'href="https://cran.r-project.org/"',
        'href="https://github.com/sorus-tools/terralink-r"',
    )
    text = text.replace("            CRAN\n", "            R project\n")
    text = text.replace(
        '        <div class="mt-5 grid gap-4">',
        '<button id="loadDemo" type="button" class="mt-4 rounded-full border border-black/10 px-4 py-2 text-xs font-semibold">Try the example landscape</button>\n        <div class="mt-5 grid gap-4">',
        1,
    )
    text = text.replace(
        '  fileInput?.addEventListener("change", handleInputPreview);',
        """  fileInput?.addEventListener("change", handleInputPreview);
  document.getElementById("loadDemo")?.addEventListener("click", async () => {
    try {
      const response = await fetch("/examples/patches.geojson");
      if (!response.ok) throw new Error("Example dataset unavailable.");
      const transfer = new DataTransfer();
      transfer.items.add(new File([await response.blob()], "example-patches.geojson", {type:"application/geo+json"}));
      fileInput.files = transfer.files;
      layerType.value = "vector";
      layerType.dispatchEvent(new Event("change"));
      document.getElementById("units").value = "metric";
      document.getElementById("units").dispatchEvent(new Event("change"));
      for (const [id,value] of Object.entries({minPatch:"0.01",budget:"2",minWidth:"20",maxSearch:"800"})) document.getElementById(id).value=value;
      if (vectorObstacleFile) vectorObstacleFile.value="";
      await handleInputPreview();
    } catch (error) { setLogLine(error.message || "Example could not be loaded.", true); }
  });""",
    )
    page.write_text(text)
    example = target / "public/examples/patches.geojson"
    example.parent.mkdir(parents=True, exist_ok=True)
    example.write_bytes((root / "conformance/fixtures/patches.geojson").read_bytes())
    (root / "web-source-provenance.json").write_text(
        json.dumps(
            {
                "origin": "Existing SORUS TerraLink tool; local working snapshot",
                "files": records,
                "adaptations": [
                    "Same-origin /api default",
                    "Standalone header/footer/layout",
                    "Company newsletter disabled",
                    "OpenStreetMap basemap",
                    "Escape output labels",
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
