"""Compatibility helpers for zero-downtime migration.

Legacy cron scripts remain untouched. These helpers let the new framework run
in shadow mode until cron cutover is explicitly enabled.
"""
from __future__ import annotations

from pathlib import Path

LEGACY_EXTRACTION = Path.home() / ".hermes" / "scripts" / "dt-dimension-extraction.py"
LEGACY_PUSH = Path.home() / ".hermes" / "scripts" / "dt-push.sh"
LEGACY_PULL = Path.home() / ".hermes" / "scripts" / "dt-pull.sh"


def legacy_paths() -> dict[str, str]:
    return {
        "extraction": str(LEGACY_EXTRACTION),
        "push": str(LEGACY_PUSH),
        "pull": str(LEGACY_PULL),
    }
