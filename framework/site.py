"""Site config helpers used by Astro and framework tooling."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_SITE_CONFIG: dict[str, Any] = {
    "default_user": "your_username",
    "display_name": "Your Name",
    "title": "Digital Twin",
    "description": "A cloneable digital-twin framework for cognitive/personality dimensions.",
    "repo_url": "https://example.invalid/your/digital-twin",
    "api_base": "https://example.invalid",
}


def load_site_config(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    path = root / "site.config.json"
    if path.exists():
        config = json.loads(path.read_text(encoding="utf-8"))
        return {**DEFAULT_SITE_CONFIG, **config}
    return dict(DEFAULT_SITE_CONFIG)
