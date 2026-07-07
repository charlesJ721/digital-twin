"""Digital Twin extraction pipeline orchestration."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib import request as urlrequest

from .config import DTConfig, load_config
from .extractors import HermesMemoryExtractor
from .detectors import ContradictionDetector
from .quality import QualityFilter, public_projection
from .schema import DimensionSchema


class DigitalTwinPipeline:
    """Orchestrates extraction → quality → contradiction → optional push."""

    def __init__(self, config: DTConfig):
        self.config = config
        self.schema = DimensionSchema.from_file(config.schema_path)
        self.extractor = HermesMemoryExtractor(config)
        self.quality = QualityFilter(config.min_confidence, config.max_insight_chars)
        self.detector = ContradictionDetector()

    def extract_text(self, since: datetime | None = None) -> str:
        return self.extractor.extract_text(since)

    def load_dimensions(self) -> dict[str, Any]:
        if self.config.dimensions_path.exists():
            return json.loads(self.config.dimensions_path.read_text(encoding="utf-8"))
        return self.initial_dimensions()

    def initial_dimensions(self) -> dict[str, Any]:
        layers = {
            lid: {
                "name": layer.name,
                "fill_rate": 0,
                "status": "empty",
                "latest_insights": [],
            }
            for lid, layer in self.schema.layers.items()
        }
        return {
            "version": "2.0",
            "last_extraction": None,
            "total_sessions_processed": 0,
            "layers": layers,
        }

    def write_dimensions(self, dimensions: dict[str, Any]) -> None:
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.config.dimensions_path.write_text(json.dumps(dimensions, ensure_ascii=False, indent=2), encoding="utf-8")
        self.config.public_dimensions_path.write_text(json.dumps(public_projection(dimensions), ensure_ascii=False, indent=2), encoding="utf-8")

    def merge_insights(self, insights: list[dict[str, Any]]) -> dict[str, Any]:
        dimensions = self.load_dimensions()
        accepted, rejected = self.quality.filter(insights)
        existing = self.detector.flatten_existing(dimensions)
        contradictions = self.detector.find(accepted, existing)

        # Use insight text as stable dedup key (not id() which depends on object identity)
        def _text_key(ins: dict[str, Any]) -> str:
            return str(ins.get("insight") or ins.get("content") or "").strip()
        blocked_texts = {_text_key(c.candidate) for c in contradictions if c.reason == "near_duplicate"}

        merged = 0
        for insight in accepted:
            if _text_key(insight) in blocked_texts:
                continue
            layer_id = self.schema.map_dimension(str(insight.get("dimension", ""))) or "4"
            layer = dimensions["layers"].setdefault(layer_id, {
                "name": self.schema.layers[layer_id].name,
                "fill_rate": 0,
                "status": "empty",
                "latest_insights": [],
            })
            layer.setdefault("latest_insights", []).append(insight)
            layer["status"] = "partial"
            layer["fill_rate"] = min(100, max(int(layer.get("fill_rate", 0)), len(layer["latest_insights"]) * 10))
            merged += 1
        dimensions["last_extraction"] = datetime.now(timezone.utc).isoformat()
        dimensions["total_sessions_processed"] = int(dimensions.get("total_sessions_processed", 0)) + merged
        self.write_dimensions(dimensions)
        return {
            "merged": merged,
            "accepted": len(accepted),
            "rejected": rejected,
            "contradictions": [c.__dict__ for c in contradictions],
            "dimensions_path": str(self.config.dimensions_path),
            "public_dimensions_path": str(self.config.public_dimensions_path),
        }

    def push_insights(self, insights: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.config.api_key:
            raise RuntimeError(f"{self.config.api_key_env} is not set")
        payload = json.dumps({"insights": insights, "source": self.config.source}, ensure_ascii=False).encode("utf-8")
        req = urlrequest.Request(
            f"{self.config.api_base}/api/user/{self.config.username}/insights",
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlrequest.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def shadow_compare(self, legacy_script: str | os.PathLike[str]) -> dict[str, Any]:
        legacy = subprocess.run(
            ["python3", str(Path(legacy_script).expanduser())],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        framework_text = self.extract_text()
        return {
            "legacy_exit": legacy.returncode,
            "legacy_head": legacy.stdout[:500],
            "framework_head": framework_text[:500],
            "matches_empty_state": legacy.stdout.strip().splitlines()[:1] == framework_text.strip().splitlines()[:1],
        }


def main(argv: list[str] | None = None) -> int:
    import sys

    parser = argparse.ArgumentParser(description="Digital Twin framework pipeline")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--extract", action="store_true", help="print LLM-ready extraction text")
    parser.add_argument("--extract-insights", action="store_true",
                        help="extract structured insights from LLM-ready text (reads from stdin)")
    parser.add_argument("--extract-text-file", help="read extraction text from file (for --extract-insights)")
    parser.add_argument("--call-llm", action="store_true",
                        help="call LLM API to generate insights (requires DEEPSEEK_API_KEY)")
    parser.add_argument("--model", default="deepseek-chat", help="LLM model for --call-llm")
    parser.add_argument("--merge-json", help="merge candidate insights from JSON file")
    parser.add_argument("--push", action="store_true", help="push merged candidate JSON to API")
    parser.add_argument("--shadow-legacy", help="compare framework extraction with a legacy script")
    args = parser.parse_args(argv)

    pipeline = DigitalTwinPipeline(load_config(args.config))
    if args.extract:
        print(pipeline.extract_text())
        return 0
    if args.extract_insights:
        from .extract_insights import build_prompt, validate_insights, parse_llm_output, call_llm

        # Read extraction text
        if args.extract_text_file:
            text = Path(args.extract_text_file).read_text(encoding="utf-8")
        else:
            text = sys.stdin.read()

        if not text.strip():
            print('{"insights": [], "error": "empty input"}', file=sys.stderr)
            return 1

        if args.call_llm:
            from .extract_insights import extract_insights as _extract
            result = _extract(text, model=args.model, validate=True)
        else:
            # Prompt-only mode: output the prompt for external LLM use
            prompt = build_prompt(text)
            print(prompt)
            return 0

        import json as _json
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.shadow_legacy:
        print(json.dumps(pipeline.shadow_compare(args.shadow_legacy), ensure_ascii=False, indent=2))
        return 0
    if args.merge_json:
        insights = json.loads(Path(args.merge_json).read_text(encoding="utf-8"))
        if isinstance(insights, dict):
            insights = insights.get("insights", [])
        result = pipeline.push_insights(insights) if args.push else pipeline.merge_insights(insights)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
