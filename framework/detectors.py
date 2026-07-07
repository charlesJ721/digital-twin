"""Contradiction and duplicate detectors for DT insights."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable


@dataclass(frozen=True)
class Contradiction:
    candidate: dict[str, Any]
    existing: dict[str, Any]
    score: float
    reason: str


class ContradictionDetector:
    """Lightweight local detector.

    This intentionally avoids network/API calls so cron and framework tests remain
    deterministic. Users can layer semantic LLM review on top when desired.
    """

    def __init__(self, duplicate_threshold: float = 0.88, tension_threshold: float = 0.55):
        self.duplicate_threshold = duplicate_threshold
        self.tension_threshold = tension_threshold
        self.negation_terms = {"not", "never", "avoid", "opposite", "不", "不是", "从不", "避免", "相反"}

    def flatten_existing(self, dimensions: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for layer_id, layer in (dimensions.get("layers") or {}).items():
            for insight in layer.get("latest_insights") or []:
                copied = dict(insight)
                copied.setdefault("layer", layer_id)
                items.append(copied)
        return items

    def similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a or "", b or "").ratio()

    def has_negation_tension(self, a: str, b: str) -> bool:
        a_has = any(term in a for term in self.negation_terms)
        b_has = any(term in b for term in self.negation_terms)
        return a_has != b_has

    def find(self, candidates: Iterable[dict[str, Any]], existing: Iterable[dict[str, Any]]) -> list[Contradiction]:
        findings: list[Contradiction] = []
        existing_list = list(existing)
        for candidate in candidates:
            c_text = str(candidate.get("insight") or candidate.get("content") or "")
            for old in existing_list:
                o_text = str(old.get("insight") or old.get("content") or "")
                score = self.similarity(c_text, o_text)
                if score >= self.duplicate_threshold:
                    findings.append(Contradiction(candidate, old, score, "near_duplicate"))
                elif score >= self.tension_threshold and self.has_negation_tension(c_text, o_text):
                    findings.append(Contradiction(candidate, old, score, "possible_negation_tension"))
        return findings
