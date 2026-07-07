#!/usr/bin/env python3
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    cfg = tmp / "config.yaml"
    data_dir = tmp / "data" / "users" / "demo"
    cfg.write_text(f"""
user:
  username: demo
  display_name: Demo User
  public: true
paths:
  project_root: {tmp}
  data_dir: {data_dir}
  hermes_state_db: /tmp/nonexistent-state.db
api:
  base_url: https://example.invalid
  api_key_env: DT_API_KEY
schema: {ROOT / 'framework/schema/7-layer-schema.yaml'}
""", encoding="utf-8")
    result = subprocess.run(["python3", "-m", "framework.cli", "init", "--config", str(cfg)], cwd=ROOT, text=True, capture_output=True, check=True)
    payload = json.loads(result.stdout)
    assert Path(payload["dimensions"]).exists()
    assert Path(payload["public_dimensions"]).exists()
    registry = json.loads((tmp / "data" / "users" / "registry.json").read_text(encoding="utf-8"))
    assert "demo" in registry["users"]
    assert not (ROOT / "data" / "users" / "demo" / "dimensions.json").exists()
print("demo isolation ok")
