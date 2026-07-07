"""Quality filtering and public projection helpers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


class QualityFilter:
    def __init__(self, min_confidence: str = "medium", max_chars: int = 2000):
        self.min_confidence = min_confidence
        self.max_chars = max_chars

    def accept(self, insight: dict[str, Any]) -> tuple[bool, str | None]:
        text = str(insight.get("insight") or insight.get("content") or "")
        confidence = str(insight.get("confidence") or "").lower()
        if len(text.strip()) < 5:
            return False, "insight text too short"
        if len(text) > self.max_chars:
            return False, "insight text too long"
        if CONFIDENCE_RANK.get(confidence, -1) < CONFIDENCE_RANK[self.min_confidence]:
            return False, "confidence below threshold"
        if not insight.get("dimension"):
            return False, "missing dimension"
        return True, None

    def filter(self, insights: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for item in insights:
            ok, reason = self.accept(item)
            if ok:
                accepted.append(item)
            else:
                bad = dict(item)
                bad["reject_reason"] = reason
                rejected.append(bad)
        return accepted, rejected


def compute_fill_rates(dimensions: dict[str, Any]) -> dict[str, int]:
    rates: dict[str, int] = {}
    for layer_id, layer in (dimensions.get("layers") or {}).items():
        insights = layer.get("latest_insights") or []
        explicit = layer.get("fill_rate")
        if isinstance(explicit, (int, float)):
            rates[str(layer_id)] = int(max(0, min(100, explicit)))
        else:
            rates[str(layer_id)] = int(max(0, min(100, len(insights) * 10)))
    return rates


def public_projection(dimensions: dict[str, Any]) -> dict[str, Any]:
    full = deepcopy(dimensions)
    layers: dict[str, Any] = {}
    for layer_id, layer in (full.get("layers") or {}).items():
        insights = layer.get("latest_insights") or []
        layers[layer_id] = {
            "name": layer.get("name"),
            "fill_rate": layer.get("fill_rate", 0),
            "status": layer.get("status", "empty"),
            "insight_count": len(insights) if isinstance(insights, list) else layer.get("insight_count", 0),
        }
    result = {
        "version": full.get("version", "2.0"),
        "last_extraction": full.get("last_extraction"),
        "total_sessions_processed": full.get("total_sessions_processed", 0),
        "layers": layers,
    }
    if "history" in full:
        result["history"] = full["history"]
    return result
