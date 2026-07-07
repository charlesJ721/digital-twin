#!/usr/bin/env python3
"""Generate unified dimension mapping from 7-layer-schema.yaml + ZH_LAYER_HINTS.

Outputs a JSON file consumable by the Cloudflare Worker, replacing its
hardcoded DIMENSION_MAP with a single-source-of-truth mapping that matches
the Python framework's schema.py behavior exactly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Work from any cwd: add the framework/ parent to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from schema import ZH_LAYER_HINTS, DimensionSchema

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "framework" / "schema" / "7-layer-schema.yaml"
OUTPUT_PATH = REPO_ROOT / "api" / "src" / "dimension-map.json"


def build_mapping() -> dict:
    schema = DimensionSchema.from_file(SCHEMA_PATH)

    exact_matches: dict[str, str] = {}

    # English keywords from schema
    for lid, layer in schema.layers.items():
        for kw in layer.keywords:
            kw_lower = kw.lower()
            if kw_lower not in exact_matches:
                exact_matches[kw_lower] = lid
        # Also add layer key and name
        if layer.key.lower() not in exact_matches:
            exact_matches[layer.key.lower()] = lid
        if layer.name.lower() not in exact_matches:
            exact_matches[layer.name.lower()] = lid

    # Chinese hints from ZH_LAYER_HINTS
    for lid, hints in ZH_LAYER_HINTS.items():
        for hint in hints:
            if hint not in exact_matches:
                exact_matches[hint] = lid

    # Regex fallback patterns (for broader matching)
    regex_fallback: dict[str, str] = {}
    for lid, hints in ZH_LAYER_HINTS.items():
        regex_fallback[lid] = "|".join(hints)

    return {
        "version": "2.0",
        "schema_ref": "framework/schema/7-layer-schema.yaml",
        "generated_at": "",  # filled by build step
        "exact_matches": exact_matches,
        "regex_fallback": regex_fallback,
    }


if __name__ == "__main__":
    import datetime

    mapping = build_mapping()
    mapping["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Generated {OUTPUT_PATH} ({len(mapping['exact_matches'])} exact matches, "
          f"{len(mapping['regex_fallback'])} regex patterns)")
