"""JSON-configured CLI; errors are machine-readable and exit nonzero."""

import argparse
import json
from pathlib import Path
import sys

from . import RunConfig, TerraLinkError, __version__, run_raster, run_vector
from .models import STRATEGIES


def main(argv=None):
    parser = argparse.ArgumentParser(prog="terralink")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--storage", type=Path)
    run = commands.add_parser("run")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "capabilities":
            print(
                json.dumps(
                    {
                        "version": __version__,
                        "strategies": STRATEGIES,
                        "modes": ["vector", "raster"],
                        "status": "alpha",
                    }
                )
            )
            return 0
        if args.command == "serve":
            from .web import create_app

            configuration = (
                {"STORAGE_ROOT": str(args.storage)} if args.storage else None
            )
            create_app(configuration).run(host=args.host, port=args.port, threaded=True)
            return 0
        request = json.loads(args.config.read_text())
        allowed = {"mode", "input", "layer", "obstacles", "parameters"}
        if set(request) - allowed:
            raise TerraLinkError(
                f"Unknown request fields: {sorted(set(request) - allowed)}"
            )
        base = args.config.resolve().parent

        def local(value):
            p = Path(value).expanduser()
            return str(p if p.is_absolute() else base / p)

        config = RunConfig(**request["parameters"])
        mode = request.get("mode", "vector")
        if mode == "vector":
            obstacles = request.get("obstacles", [])
            if isinstance(obstacles, str):
                obstacles = [obstacles]
            result = run_vector(
                local(request["input"]),
                args.output,
                config,
                obstacles=[local(path) for path in obstacles],
                layer=request.get("layer"),
            )
        elif mode == "raster":
            result = run_raster(local(request["input"]), args.output, config)
        else:
            raise TerraLinkError("mode must be vector or raster")
        print(json.dumps(result.to_dict(), allow_nan=False))
        return 0
    except (TerraLinkError, ValueError, TypeError, KeyError, OSError) as exc:
        print(
            json.dumps({"error": type(exc).__name__, "message": str(exc)}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
