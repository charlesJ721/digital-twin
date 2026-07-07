"""Bootstrap CLI for Digital Twin v2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import load_config
from .pipeline import DigitalTwinPipeline
from .quality import public_projection


def init_user(config_path: str, *, force: bool = False) -> dict[str, Any]:
    cfg = load_config(config_path)
    pipeline = DigitalTwinPipeline(cfg)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    dims_path = cfg.dimensions_path
    if dims_path.exists() and not force:
        dimensions = json.loads(dims_path.read_text(encoding="utf-8"))
    else:
        dimensions = pipeline.initial_dimensions()
        dims_path.write_text(json.dumps(dimensions, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg.public_dimensions_path.write_text(json.dumps(public_projection(dimensions), ensure_ascii=False, indent=2), encoding="utf-8")

    registry_path = cfg.registry_path
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    else:
        registry = {"users": {}}
    users = registry.setdefault("users", {})
    existing_user = dict(users.get(cfg.username, {}))
    existing_user.update({
        "display_name": cfg.display_name,
        "public": cfg.public,
    })
    users[cfg.username] = existing_user
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "username": cfg.username,
        "dimensions": str(dims_path),
        "public_dimensions": str(cfg.public_dimensions_path),
        "registry": str(registry_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dt", description="Digital Twin v2 CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="initialize a user data directory")
    init.add_argument("--config", default="config.yaml")
    init.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "init":
        print(json.dumps(init_user(args.config, force=args.force), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
