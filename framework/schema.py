"""Dimension schema authority for Digital Twin v2."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

ZH_LAYER_HINTS: dict[str, list[str]] = {
    "1": ["人格", "特质", "动机", "驱动", "恐惧", "气质"],
    "2": ["推理", "认知", "思维", "决策", "学习", "创造", "元认知"],
    "3": ["价值", "信念", "伦理", "世界观", "需求"],
    "4": ["行为", "习惯", "模式", "防御", "能量", "周期", "节律"],
    "5": ["知识", "专长", "信息", "领域"],
    "6": ["社会", "关系", "互动", "信任", "影响", "亲密", "合作"],
    "7": ["叙事", "自我", "身份", "人生", "转折", "故事"],
}


@dataclass(frozen=True)
class Layer:
    id: str
    key: str
    name: str
    description: str
    keywords: tuple[str, ...]


class DimensionSchema:
    """Loads and maps the canonical seven-layer DT schema."""

    def __init__(self, layers: Mapping[str, Layer], insight_rules: Mapping[str, Any] | None = None):
        self.layers = dict(layers)
        self.insight_rules = dict(insight_rules or {})

    @classmethod
    def from_file(cls, path: str | Path) -> "DimensionSchema":
        if yaml is None:
            raise RuntimeError("PyYAML is required to read schema files")
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        raw_layers = data.get("layers", {})
        layers: dict[str, Layer] = {}
        for lid, raw in raw_layers.items():
            layers[str(lid)] = Layer(
                id=str(lid),
                key=str(raw.get("key", lid)),
                name=str(raw.get("name", lid)),
                description=str(raw.get("description", "")),
                keywords=tuple(str(k).lower() for k in raw.get("keywords", [])),
            )
        if set(layers) != {"1", "2", "3", "4", "5", "6", "7"}:
            raise ValueError("schema must define layers 1 through 7")
        return cls(layers, data.get("insight", {}))

    def map_dimension(self, dimension: str) -> str | None:
        text = (dimension or "").strip()
        if not text:
            return None
        arrow = re.search(r"(?:L|layer\s*)([1-7])", text, flags=re.I)
        if arrow:
            return arrow.group(1)
        lowered = text.lower()
        for lid, layer in self.layers.items():
            if layer.key.lower() in lowered or layer.name.lower() in lowered:
                return lid
            if any(keyword and keyword in lowered for keyword in layer.keywords):
                return lid
        for lid, hints in ZH_LAYER_HINTS.items():
            if any(h in text for h in hints):
                return lid
        return None

    def validate_dimension(self, dimension: str) -> bool:
        return self.map_dimension(dimension) is not None


def validate_dimension(dimension: str, schema_path: str | Path | None = None) -> bool:
    path = Path(schema_path or Path(__file__).parent / "schema" / "7-layer-schema.yaml")
    return DimensionSchema.from_file(path).validate_dimension(dimension)
