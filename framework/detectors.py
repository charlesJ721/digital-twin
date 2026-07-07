"""Contradiction and duplicate detectors for DT insights.

Provides two tiers:
- Lightweight: SequenceMatcher + negation terms (offline, deterministic)
- Semantic: embedding-based similarity + memory_type conflict detection
  Falls back to lightweight when API is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import os
from typing import Any, Iterable
from urllib import request as urlrequest

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Contradiction:
    candidate: dict[str, Any]
    existing: dict[str, Any]
    score: float
    reason: str


# ---------------------------------------------------------------------------
# Lightweight detector (offline, deterministic — kept as fallback)
# ---------------------------------------------------------------------------


class LightweightDetector:
    """SequenceMatcher-based dedup + negation tension.

    Intentionally avoids network/API calls so cron and framework tests
    remain deterministic.
    """

    def __init__(self, duplicate_threshold: float = 0.88, tension_threshold: float = 0.55):
        self.duplicate_threshold = duplicate_threshold
        self.tension_threshold = tension_threshold
        self.negation_terms = {
            "not", "never", "avoid", "opposite",
            "不", "不是", "从不", "避免", "相反",
        }

    def similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a or "", b or "").ratio()

    def has_negation_tension(self, a: str, b: str) -> bool:
        a_has = any(term in a for term in self.negation_terms)
        b_has = any(term in b for term in self.negation_terms)
        return a_has != b_has

    def find(
        self,
        candidates: Iterable[dict[str, Any]],
        existing: Iterable[dict[str, Any]],
    ) -> list[Contradiction]:
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


# ---------------------------------------------------------------------------
# Semantic detector (embedding-based, API-enhanced)
# ---------------------------------------------------------------------------


# Memory types that represent "what the user says about themselves" (declarative)
DECLARATIVE_TYPES = {"fact", "preference", "policy"}

# Memory types that represent "what the user actually did" (behavioral)
BEHAVIORAL_TYPES = {"episodic", "trace"}

# OpenRouter embedding endpoint
EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "openai/text-embedding-3-small"


def _get_openrouter_key() -> str:
    """Try to find an OpenRouter API key from environment or Hermes config."""
    # Check env vars
    for var in ("OPENROUTER_API_KEY", "OR_API_KEY"):
        key = os.environ.get(var, "")
        if key:
            return key
    # Try Hermes config
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    if os.path.exists(config_path):
        try:
            import yaml
            cfg = yaml.safe_load(open(config_path))
            providers = cfg.get("providers", {})
            for p in providers.values() if isinstance(providers, dict) else []:
                if isinstance(p, dict) and "openrouter" in str(p.get("provider", "")).lower():
                    key = p.get("api_key", "")
                    if key:
                        return key
        except Exception:
            pass
    return ""


def _get_proxy() -> str | None:
    """Get OpenRouter proxy URL from environment variables."""
    return os.environ.get("TOF_OPENROUTER_PROXY") or os.environ.get("https_proxy") or None


def _embed_batch(texts: list[str], api_key: str | None = None) -> list[list[float]] | None:
    """Embed a batch of texts via OpenRouter. Returns None on failure."""
    key = api_key or _get_openrouter_key()
    if not key:
        return None

    proxy = _get_proxy()
    proxy_handler = urlrequest.ProxyHandler({"https": proxy}) if proxy else None
    opener = urlrequest.build_opener(proxy_handler) if proxy_handler else urlrequest.build_opener()

    payload = json.dumps({
        "model": EMBEDDING_MODEL,
        "input": texts,
    }).encode("utf-8")

    req = urlrequest.Request(
        EMBEDDING_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with opener.open(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    data = body.get("data", [])
    if not data:
        return None

    # Sort by index to preserve input order
    data_sorted = sorted(data, key=lambda x: x.get("index", 0))
    return [item.get("embedding", []) for item in data_sorted]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = (sum(x * x for x in a)) ** 0.5
    norm_b = (sum(x * x for x in b)) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class ContradictionDetector:
    """Primary detector: embedding similarity + memory_type conflict.

    Falls back to LightweightDetector when embedding API is unavailable.
    """

    def __init__(
        self,
        duplicate_threshold: float = 0.88,
        tension_threshold: float = 0.55,
        semantic_duplicate_threshold: float = 0.85,
        semantic_conflict_threshold: float = 0.72,
        api_key: str | None = None,
    ):
        self.duplicate_threshold = duplicate_threshold
        self.tension_threshold = tension_threshold
        self.semantic_duplicate_threshold = semantic_duplicate_threshold
        self.semantic_conflict_threshold = semantic_conflict_threshold
        self.api_key = api_key
        self._lightweight = LightweightDetector(duplicate_threshold, tension_threshold)
        self._embedding_available: bool | None = None  # lazily determined

    def flatten_existing(self, dimensions: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for layer_id, layer in (dimensions.get("layers") or {}).items():
            for insight in layer.get("latest_insights") or []:
                copied = dict(insight)
                copied.setdefault("layer", layer_id)
                items.append(copied)
        return items

    def _text(self, insight: dict[str, Any]) -> str:
        return str(insight.get("insight") or insight.get("content") or "")

    def _memory_type(self, insight: dict[str, Any]) -> str:
        return str(insight.get("memory_type") or insight.get("state") or "")

    def _check_embedding_available(self) -> bool:
        """Lazy check: try embedding a single short text."""
        if self._embedding_available is not None:
            return self._embedding_available
        result = _embed_batch(["test"], self.api_key)
        self._embedding_available = result is not None and len(result) > 0
        return self._embedding_available

    def find(
        self,
        candidates: Iterable[dict[str, Any]],
        existing: Iterable[dict[str, Any]],
    ) -> list[Contradiction]:
        """Detect duplicates and contradictions.

        Tries embedding path first; falls back to lightweight on failure.
        """
        existing_list = list(existing)
        if not existing_list:
            return []

        if self._check_embedding_available():
            return self._find_semantic(candidates, existing_list)
        return self._lightweight.find(candidates, existing_list)

    def _find_semantic(
        self,
        candidates: Iterable[dict[str, Any]],
        existing_list: list[dict[str, Any]],
    ) -> list[Contradiction]:
        """Embedding-based detection with memory_type conflict awareness."""
        cand_list = list(candidates)

        # Collect all texts for batch embedding
        all_texts = [self._text(c) for c in cand_list] + [self._text(e) for e in existing_list]
        all_vectors = _embed_batch(all_texts, self.api_key)

        if all_vectors is None or len(all_vectors) != len(all_texts):
            # Fall back to lightweight on partial failure
            return self._lightweight.find(candidates, existing_list)

        n_candidates = len(cand_list)
        cand_vecs = all_vectors[:n_candidates]
        exist_vecs = all_vectors[n_candidates:]

        findings: list[Contradiction] = []

        for i, candidate in enumerate(cand_list):
            cv = cand_vecs[i]
            c_type = self._memory_type(candidate)
            c_text = self._text(candidate)

            for j, old in enumerate(existing_list):
                ev = exist_vecs[j]
                score = _cosine_sim(cv, ev)
                o_type = self._memory_type(old)
                o_text = self._text(old)

                c_is_decl = c_type in DECLARATIVE_TYPES
                c_is_behav = c_type in BEHAVIORAL_TYPES
                o_is_decl = o_type in DECLARATIVE_TYPES
                o_is_behav = o_type in BEHAVIORAL_TYPES
                cross_type = (c_is_decl and o_is_behav) or (c_is_behav and o_is_decl)

                # Cognitive conflict: cross-type pairs with high similarity
                # take priority over near_duplicate. Genuine contradictions
                # (e.g. "says X" vs "does ¬X") naturally share topic space and
                # produce high cosine scores — checking conflict first prevents
                # them from being swallowed by the duplicate threshold.
                if cross_type and score >= self.semantic_conflict_threshold:
                    findings.append(Contradiction(
                        candidate, old, round(score, 4),
                        "semantic_conflict_decl_vs_behav",
                    ))
                    continue

                # Near-duplicate: very high similarity, same memory type
                if score >= self.semantic_duplicate_threshold:
                    findings.append(Contradiction(candidate, old, round(score, 4), "near_duplicate"))
                    continue

                # Negation tension as additional signal (same-type, medium similarity)
                if score >= self.semantic_conflict_threshold:
                    if self._lightweight.has_negation_tension(c_text, o_text):
                        findings.append(Contradiction(
                            candidate, old, round(score, 4),
                            "possible_negation_tension",
                        ))

        return findings


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

# Old code that does `from .detectors import ContradictionDetector` still works.
# ContradictionDetector is now the semantic-enhanced version above.
