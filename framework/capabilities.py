"""
capabilities.py — 运行时能力探测。

替代硬编码假设，动态发现 Hermes/平台能力。
设计源自 Cogito Engine 的 EnvSensor / Capability Probing 模式。

探测维度：
  - Hermes state.db 位置（跨 profile / 自定义路径）
  - session_search 可用性
  - memory 系统状态
  - 文件系统访问

零外部依赖，纯标准库。优雅降级无处不在。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import sqlite3
from typing import Optional


@dataclass
class HostCapabilities:
    """运行时可用的平台能力快照。"""

    # Hermes
    hermes_home: Path
    hermes_state_db: Optional[Path] = None
    hermes_memory_enabled: bool = False
    hermes_profiles: list[str] = field(default_factory=list)
    active_profile: Optional[str] = None

    # 文件系统
    home_dir: Path = field(default_factory=Path.home)
    writable_data_dir: Optional[Path] = None

    # 诊断
    probe_errors: list[str] = field(default_factory=list)
    probed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "hermes_home": str(self.hermes_home),
            "state_db": str(self.hermes_state_db) if self.hermes_state_db else None,
            "memory_enabled": self.hermes_memory_enabled,
            "profiles": self.hermes_profiles,
            "active_profile": self.active_profile,
            "errors": self.probe_errors,
        }


def probe_hermes_home() -> Path:
    """探测 Hermes 主目录（支持自定义 HERMES_HOME 环境变量）。"""
    custom = os.environ.get("HERMES_HOME", "")
    if custom:
        p = Path(custom).expanduser()
        if p.is_dir():
            return p
    default = Path.home() / ".hermes"
    if default.is_dir():
        return default
    return default  # 返回默认值，后续探测可能失败


def probe_state_db(hermes_home: Path) -> Optional[Path]:
    """探测 state.db 位置。

    尝试路径：
      1. <hermes_home>/state.db
      2. <hermes_home>/sessions/state.db (旧格式)
    """
    candidates = [
        hermes_home / "state.db",
        hermes_home / "sessions" / "state.db",
    ]
    for p in candidates:
        if p.is_file():
            try:
                conn = sqlite3.connect(str(p))
                conn.execute("SELECT 1 FROM sessions LIMIT 1")
                conn.close()
                return p
            except Exception:
                continue
    return None


def probe_profiles(hermes_home: Path) -> tuple[list[str], Optional[str]]:
    """探测 Hermes profiles。

    Returns:
        (profile_names, active_profile_name_or_None)
    """
    profiles_dir = hermes_home / "profiles"
    if not profiles_dir.is_dir():
        return [], None

    names = sorted(
        d.name for d in profiles_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    # 检查活跃 profile（从 config.yaml 或环境变量）
    active = os.environ.get("HERMES_PROFILE")
    if not active:
        config_path = hermes_home / "config.yaml"
        if config_path.is_file():
            try:
                import yaml
                cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                active = cfg.get("profile", {}).get("default") or cfg.get("active_profile")
            except Exception:
                pass

    return names, active


def probe_memory(hermes_home: Path) -> bool:
    """探测 memory 系统是否启用。

    检查：是否存在 memory/ 目录且有内容，
    或 MEMORY.md / USER.md 文件存在。
    """
    memory_dir = hermes_home / "memory"
    if memory_dir.is_dir() and any(memory_dir.iterdir()):
        return True
    # 备用检查：profile 级别的 memory
    profiles_dir = hermes_home / "profiles"
    if profiles_dir.is_dir():
        for profile in profiles_dir.iterdir():
            p_memory = profile / "memory"
            if p_memory.is_dir() and any(p_memory.iterdir()):
                return True
    return False


def probe_all(hermes_home: Optional[Path] = None) -> HostCapabilities:
    """执行全维度能力探测。

    Args:
        hermes_home: 强制指定 Hermes 主目录，None 则自动探测。

    Returns:
        HostCapabilities 快照。
    """
    from datetime import datetime, timezone

    caps = HostCapabilities(
        hermes_home=hermes_home or probe_hermes_home(),
        probed_at=datetime.now(timezone.utc).isoformat(),
    )

    # 1. state.db
    try:
        caps.hermes_state_db = probe_state_db(caps.hermes_home)
    except Exception as e:
        caps.probe_errors.append(f"state_db: {e}")

    # 2. profiles
    try:
        caps.hermes_profiles, caps.active_profile = probe_profiles(caps.hermes_home)
    except Exception as e:
        caps.probe_errors.append(f"profiles: {e}")

    # 3. memory
    try:
        caps.hermes_memory_enabled = probe_memory(caps.hermes_home)
    except Exception as e:
        caps.probe_errors.append(f"memory: {e}")

    return caps


# ── 使用示例 ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    caps = probe_all()
    print(json.dumps(caps.to_dict(), ensure_ascii=False, indent=2))
    if caps.probe_errors:
        print(f"\n⚠️  {len(caps.probe_errors)} probe error(s):")
        for e in caps.probe_errors:
            print(f"  - {e}")
