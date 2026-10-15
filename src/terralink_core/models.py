"""Public configurations use explicit display units; engine conversion is recorded."""

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from typing import Any

STRATEGIES = {
    "most_connected_networks_2": "Most Connected Networks A",
    "most_connected_networks": "Most Connected Networks B",
    "largest_single_network": "Largest Single Network",
    "landscape_fluidity": "Landscape Fluidity",
}


class TerraLinkError(ValueError):
    """An invalid request or failed analytical run, suitable for API/CLI reporting."""


@dataclass(frozen=True)
class RunConfig:
    budget_area: float
    min_corridor_width: float
    max_search_distance: float
    strategy: str = "most_connected_networks"
    min_patch_size: float = 0.1
    units: str = "metric"
    grid_resolution: float = 10.0
    routing_enabled: bool = False
    analysis_crs: str | None = None
    patch_values: tuple[float, ...] = (1.0,)
    obstacle_values: tuple[float, ...] = ()
    patch_range: tuple[float, float] | None = None
    obstacle_range: tuple[float, float] | None = None
    patch_connectivity: int = 4
    allow_bottlenecks: bool = True
    value_tolerance: float = 1e-6
    band: int = 1
    seed: int = 0
    engine_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.strategy not in STRATEGIES:
            raise TerraLinkError(
                f"Unknown strategy {self.strategy!r}; choose one of {', '.join(STRATEGIES)}"
            )
        if self.units not in {"metric", "imperial", "pixels"}:
            raise TerraLinkError("units must be metric, imperial, or pixels")
        for name in [
            "budget_area",
            "min_corridor_width",
            "grid_resolution",
            "value_tolerance",
        ]:
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise TerraLinkError(f"{name} must be a finite positive number")
        if (
            isinstance(self.min_patch_size, bool)
            or not isinstance(self.min_patch_size, (int, float))
            or not math.isfinite(self.min_patch_size)
            or self.min_patch_size < 0
        ):
            raise TerraLinkError("min_patch_size must be finite and nonnegative")
        if (
            isinstance(self.max_search_distance, bool)
            or not isinstance(self.max_search_distance, (int, float))
            or not math.isfinite(self.max_search_distance)
            or self.max_search_distance < 0
        ):
            raise TerraLinkError(
                "max_search_distance must be finite and nonnegative (0 selects automatic search)"
            )
        if self.patch_connectivity not in {4, 8}:
            raise TerraLinkError("patch_connectivity must be 4 or 8")
        if (
            not isinstance(self.band, int)
            or isinstance(self.band, bool)
            or self.band < 1
        ):
            raise TerraLinkError("band must be a positive integer")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise TerraLinkError("seed must be an integer")
        if not isinstance(self.routing_enabled, bool) or not isinstance(
            self.allow_bottlenecks, bool
        ):
            raise TerraLinkError(
                "routing_enabled and allow_bottlenecks must be booleans"
            )
        for name in ["patch_values", "obstacle_values"]:
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or any(
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                for v in values
            ):
                raise TerraLinkError(f"{name} must contain finite numeric values")
        for name in ["patch_range", "obstacle_range"]:
            values = getattr(self, name)
            if values is not None and (
                not isinstance(values, (tuple, list))
                or len(values) != 2
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not math.isfinite(v)
                    for v in values
                )
                or values[0] > values[1]
            ):
                raise TerraLinkError(f"{name} must be a finite ascending pair")
        if not self.patch_values and self.patch_range is None:
            raise TerraLinkError("Specify patch_values or patch_range")
        if not isinstance(self.engine_options, dict):
            raise TerraLinkError("engine_options must be an object")
        if self.units == "pixels":
            for name in [
                "budget_area",
                "min_patch_size",
                "min_corridor_width",
                "max_search_distance",
            ]:
                if not float(getattr(self, name)).is_integer():
                    raise TerraLinkError(
                        f"{name} must use whole-cell values in pixels mode; use metric units for fractional dimensions"
                    )

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class RunResult:
    output_dir: Path
    corridors_path: Path
    corridor_layer: str
    network_layer: str
    stats: dict[str, Any]
    manifest_path: Path
    metrics_path: Path

    def to_dict(self):
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(self).items()
        }
