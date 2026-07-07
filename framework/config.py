"""Configuration loading for the Digital Twin framework."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from typing import Any, Mapping

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - only used on minimal Python installs
    yaml = None

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand_env_vars(value: Any) -> Any:
    """Recursively expand ${VAR:-default} strings and user home markers."""
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            return os.environ.get(name, default or "")
        expanded = _ENV_PATTERN.sub(repl, value)
        return os.path.expanduser(expanded)
    if isinstance(value, list):
        return [expand_env_vars(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    return value


@dataclass(frozen=True)
class DTConfig:
    username: str
    display_name: str
    public: bool
    project_root: Path
    data_dir: Path
    hermes_state_db: Path
    api_base: str
    api_key_env: str
    schema_path: Path
    min_user_messages: int = 5
    max_messages_per_session: int = 500
    source: str = "hermes-cron"
    min_confidence: str = "medium"
    max_insight_chars: int = 2000

    @property
    def dimensions_path(self) -> Path:
        return self.data_dir / "dimensions.json"

    @property
    def public_dimensions_path(self) -> Path:
        return self.data_dir / "dimensions-public.json"

    @property
    def registry_path(self) -> Path:
        return self.project_root / "data" / "users" / "registry.json"

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    def validate(self) -> None:
        if not self.username or not re.fullmatch(r"[a-zA-Z0-9_-]+", self.username):
            raise ValueError("user.username must contain only letters, numbers, '_' or '-'")
        if not self.display_name:
            raise ValueError("user.display_name is required")
        if self.min_confidence not in {"high", "medium", "low"}:
            raise ValueError("quality.min_confidence must be high, medium or low")
        if self.max_insight_chars < 80:
            raise ValueError("quality.max_insight_chars is too low")


def _read_mapping(path: Path) -> Mapping[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is None:
        raise RuntimeError("PyYAML is required to read YAML config files")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, Mapping):
        raise ValueError(f"config must be a mapping: {path}")
    return data


def load_config(path: str | os.PathLike[str] = "config.yaml") -> DTConfig:
    """Load, expand and validate a DT config file."""
    config_path = Path(path).expanduser().resolve()
    raw = expand_env_vars(dict(_read_mapping(config_path)))

    user = raw.get("user", {})
    paths = raw.get("paths", {})
    api = raw.get("api", {})
    extraction = raw.get("extraction", {})
    quality = raw.get("quality", {})

    project_root = Path(paths.get("project_root", config_path.parent)).expanduser()
    if not project_root.is_absolute():
        project_root = (config_path.parent / project_root).resolve()
    data_dir = Path(paths.get("data_dir", project_root / "data" / "users" / user.get("username", "user"))).expanduser()
    if not data_dir.is_absolute():
        data_dir = (project_root / data_dir).resolve()
    schema_path = Path(raw.get("schema", project_root / "framework" / "schema" / "7-layer-schema.yaml")).expanduser()
    if not schema_path.is_absolute():
        schema_path = (project_root / schema_path).resolve()

    cfg = DTConfig(
        username=str(user.get("username", os.environ.get("DT_USERNAME", ""))),
        display_name=str(user.get("display_name", os.environ.get("DT_DISPLAY_NAME", ""))),
        public=bool(user.get("public", True)),
        project_root=project_root,
        data_dir=data_dir,
        hermes_state_db=Path(paths.get("hermes_state_db", "~/.hermes/state.db")).expanduser(),
        api_base=str(api.get("base_url", "")).rstrip("/"),
        api_key_env=str(api.get("api_key_env", "DT_API_KEY")),
        schema_path=schema_path,
        min_user_messages=int(extraction.get("min_user_messages", 5)),
        max_messages_per_session=int(extraction.get("max_messages_per_session", 500)),
        source=str(extraction.get("source", "hermes-cron")),
        min_confidence=str(quality.get("min_confidence", "medium")),
        max_insight_chars=int(quality.get("max_insight_chars", 2000)),
    )
    cfg.validate()
    return cfg
