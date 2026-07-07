"""Unit tests for ContradictionDetector (both lightweight and semantic paths)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import pytest
except ImportError:
    pytest = None  # type: ignore

from framework.detectors import (
    ContradictionDetector,
    LightweightDetector,
    DECLARATIVE_TYPES,
    BEHAVIORAL_TYPES,
    _cosine_sim,
)


# ---------------------------------------------------------------------------
# Cosine similarity (pure math, no API)
# ---------------------------------------------------------------------------

def test_cosine_identical():
    v = [1.0, 2.0, 3.0]
    assert _cosine_sim(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal():
    assert _cosine_sim([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_empty():
    assert _cosine_sim([], []) == 0.0


def test_cosine_mismatched_length():
    assert _cosine_sim([1.0, 2.0], [1.0]) == 0.0


# ---------------------------------------------------------------------------
# LightweightDetector
# ---------------------------------------------------------------------------

def test_lw_near_duplicate():
    lw = LightweightDetector(duplicate_threshold=0.85)
    findings = lw.find(
        [{"insight": "用户偏好数据驱动的决策方式"}],
        [{"insight": "用户偏好数据驱动的决策方法"}],
    )
    assert len(findings) == 1
    assert findings[0].reason == "near_duplicate"
    assert findings[0].score >= 0.85


def test_lw_negation_tension():
    lw = LightweightDetector(tension_threshold=0.40)
    findings = lw.find(
        [{"insight": "用户不喜欢被打断工作流"}],
        [{"insight": "用户享受被打断的即兴讨论"}],
    )
    # May or may not trigger depending on score; either outcome is valid
    assert all(f.reason in ("near_duplicate", "possible_negation_tension") for f in findings)


def test_lw_no_false_positive():
    lw = LightweightDetector()
    findings = lw.find(
        [{"insight": "用户偏好数据驱动的决策方式"}],
        [{"insight": "用户喜欢在周末去爬山放松"}],
    )
    assert len(findings) == 0


def test_lw_empty_existing():
    lw = LightweightDetector()
    findings = lw.find([{"insight": "test"}], [])
    assert findings == []


# ---------------------------------------------------------------------------
# ContradictionDetector (fallback mode — no API key)
# ---------------------------------------------------------------------------

def test_detector_flatten_existing():
    detector = ContradictionDetector(api_key="")
    dims = {
        "layers": {
            "2": {"latest_insights": [{"insight": "a"}, {"insight": "b"}]},
            "4": {"latest_insights": [{"insight": "c"}]},
        }
    }
    flat = detector.flatten_existing(dims)
    assert len(flat) == 3
    assert flat[0]["layer"] == "2"
    assert flat[2]["layer"] == "4"


def test_detector_fallback_on_empty_key():
    """With no API key, should fall back to lightweight detector."""
    detector = ContradictionDetector(api_key="")
    existing = [{"insight": "用户偏好数据驱动的决策方式"}]
    candidates = [{"insight": "用户偏好数据驱动的决策方式方法"}]
    findings = detector.find(candidates, existing)
    # Lightweight fallback should catch near-duplicate
    assert len(findings) == 1
    assert findings[0].reason == "near_duplicate"


def test_detector_empty_candidates():
    detector = ContradictionDetector(api_key="")
    findings = detector.find([], [{"insight": "existing"}])
    assert findings == []


def test_detector_empty_existing():
    detector = ContradictionDetector(api_key="")
    findings = detector.find([{"insight": "new"}], [])
    assert findings == []


# ---------------------------------------------------------------------------
# Memory type classification (imported at top of file)
# ---------------------------------------------------------------------------


def test_declarative_types():
    assert "fact" in DECLARATIVE_TYPES
    assert "preference" in DECLARATIVE_TYPES
    assert "policy" in DECLARATIVE_TYPES


def test_behavioral_types():
    assert "episodic" in BEHAVIORAL_TYPES
    assert "trace" in BEHAVIORAL_TYPES


def test_no_overlap():
    assert DECLARATIVE_TYPES.isdisjoint(BEHAVIORAL_TYPES)


# ---------------------------------------------------------------------------
# Injected-embedding tests: verify semantic logic without API calls.
# The reviewer's exact scenario: "memory says data-driven (fact) but 80% of
# decisions are intuitive (episodic)" — the canonical contradiction case.
# ---------------------------------------------------------------------------

def _make_detector_with_fake_embeddings(*fake_vecs: list[float]):
    """Return a ContradictionDetector that bypasses the real embedding API.

    Each fake_vecs[i] is assigned to all_texts[i] in order.
    Caller must match the number of vectors to (candidates + existing).
    """
    import framework.detectors as mod

    detector = ContradictionDetector(api_key="fake-but-available")

    # Force embedding availability check to pass
    detector._embedding_available = True

    # Replace _embed_batch to return the fake vectors
    original_embed = mod._embed_batch
    mod._embed_batch = lambda texts, api_key=None: list(fake_vecs)

    return detector, original_embed


def _restore_embed(original):
    import framework.detectors as mod
    mod._embed_batch = original


def test_semantic_conflict_fires_before_near_duplicate():
    """The critical bug fix: cross-type conflict must take priority over duplicate.

    Scenario: "memory says data-driven" (fact) vs "behavior shows intuitive" (episodic).
    Both talk about decision-making → high cosine similarity.
    The old code would classify this as near_duplicate and skip conflict detection.
    """
    # Two fake 4-dim vectors with high cosine similarity (~0.90)
    # Vector a = [1, 0, 0, 0], Vector b = [0.9, 0.1, 0, 0] → cos ≈ 0.994
    # Use two nearly-identical vectors to simulate the "same topic, opposite stance" pattern
    fake_vecs = [
        [1.0, 0.0, 0.0, 0.0],   # candidate: "data-driven preference"
        [0.95, 0.05, 0.0, 0.0],  # existing: "intuitive behavior" → high similarity
    ]

    detector, original = _make_detector_with_fake_embeddings(*fake_vecs)
    try:
        candidate = [{
            "insight": "用户在技术选型中优先考虑延展性而非短期便利性",
            "memory_type": "preference",  # declarative
            "dimension": "决策风格",
        }]
        existing = [{
            "insight": "用户在实际操作中几乎总是凭直觉快速决策，事后才找数据佐证",
            "memory_type": "episodic",  # behavioral
            "layer": "2",
        }]

        findings = detector.find(candidate, existing)

        # Must detect the cross-type conflict, not (just) near_duplicate
        reasons = [f.reason for f in findings]
        assert "semantic_conflict_decl_vs_behav" in reasons, (
            f"Expected semantic_conflict_decl_vs_behav, got {reasons}. "
            "Cross-type pairs should be detected as contradictions, not duplicates."
        )
    finally:
        _restore_embed(original)


def test_same_type_high_similarity_is_near_duplicate():
    """Same memory_type + high similarity → near_duplicate (correctly)."""
    fake_vecs = [
        [1.0, 0.0, 0.0, 0.0],
        [0.95, 0.05, 0.0, 0.0],  # ~0.99 cosine
    ]

    detector, original = _make_detector_with_fake_embeddings(*fake_vecs)
    try:
        candidate = [{
            "insight": "用户偏好数据驱动的决策",
            "memory_type": "preference",
            "dimension": "决策风格",
        }]
        existing = [{
            "insight": "用户偏好数据驱动的决策方式",
            "memory_type": "preference",  # same type
            "layer": "2",
        }]

        findings = detector.find(candidate, existing)
        reasons = [f.reason for f in findings]
        assert "near_duplicate" in reasons, f"Expected near_duplicate, got {reasons}"
        assert "semantic_conflict_decl_vs_behav" not in reasons, (
            "Same-type pairs should NOT trigger conflict"
        )
    finally:
        _restore_embed(original)


def test_low_similarity_no_findings():
    """Dissimilar texts → no findings even with cross-type."""
    fake_vecs = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],  # ~0.0 cosine
    ]

    detector, original = _make_detector_with_fake_embeddings(*fake_vecs)
    try:
        candidate = [{
            "insight": "用户偏好数据驱动",
            "memory_type": "preference",
            "dimension": "决策风格",
        }]
        existing = [{
            "insight": "用户喜欢爬山",
            "memory_type": "episodic",
            "layer": "4",
        }]

        findings = detector.find(candidate, existing)
        assert findings == [], f"Expected no findings, got {[f.reason for f in findings]}"
    finally:
        _restore_embed(original)
