"""Package the built Astro application for the optional Python HTTP service."""

from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
subprocess.run(["npm", "run", "build"], cwd=root / "apps/web", check=True)
destination = root / "src/terralink_core/web_static"
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(root / "apps/web/dist", destination)
print(f"Packaged web UI in {destination}")
