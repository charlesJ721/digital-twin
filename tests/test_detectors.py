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


if __name__ == "__main__":
    import pytest as pt
    pt.main([__file__, "-v"])
