"""TerraLink standalone analysis API."""

__version__ = "0.1.0a1"
ALGORITHM_PROFILE = "qgis-1.8.3-extraction-alpha"
UPSTREAM_REVISION = "2cb4a568e8990d7834019ce9bdbdfb7f3ae893f4"

from .models import RunConfig, RunResult, TerraLinkError


def run_vector(
    input_path, output_dir, config, *, obstacles=None, layer=None, progress=None
):
    from .api import run_vector as implementation

    return implementation(
        input_path,
        output_dir,
        config,
        obstacles=obstacles,
        layer=layer,
        progress=progress,
    )


def run_raster(input_path, output_dir, config, *, progress=None):
    from .api import run_raster as implementation

    return implementation(input_path, output_dir, config, progress=progress)


__all__ = ["RunConfig", "RunResult", "TerraLinkError", "run_vector", "run_raster"]
