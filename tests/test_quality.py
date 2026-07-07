"""Unit tests for QualityFilter and public_projection."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.quality import QualityFilter, compute_fill_rates, public_projection


# ---------------------------------------------------------------------------
# QualityFilter.accept
# ---------------------------------------------------------------------------

def _insight(**overrides):
    base = {"date": "2026-07-07", "dimension": "决策风格", "insight": "一条有意义的洞察文本", "confidence": "high", "evidence": "原文引用"}
    base.update(overrides)
    return base


def test_accept_valid():
    qf = QualityFilter()
    ok, reason = qf.accept(_insight())
    assert ok
    assert reason is None


def test_reject_short_text():
    qf = QualityFilter()
    ok, reason = qf.accept(_insight(insight="短"))
    assert not ok
    assert "short" in reason


def test_reject_long_text():
    qf = QualityFilter(max_chars=5)
    ok, reason = qf.accept(_insight(insight="这是一条超过了限制的文本"))
    assert not ok
    assert "long" in reason


def test_reject_low_confidence():
    qf = QualityFilter(min_confidence="medium")
    ok, reason = qf.accept(_insight(confidence="low"))
    assert not ok
    assert "confidence" in reason


def test_accept_medium_with_low_threshold():
    qf = QualityFilter(min_confidence="low")
    ok, _ = qf.accept(_insight(confidence="medium"))
    assert ok


def test_reject_missing_dimension():
    qf = QualityFilter()
    ok, reason = qf.accept(_insight(dimension=""))
    assert not ok
    assert "dimension" in reason


def test_reject_empty_confidence():
    qf = QualityFilter(min_confidence="medium")
    ok, reason = qf.accept(_insight(confidence=""))
    assert not ok


# ---------------------------------------------------------------------------
# QualityFilter.filter (batch)
# ---------------------------------------------------------------------------

def test_filter_batch():
    qf = QualityFilter()
    items = [
        _insight(),
        _insight(insight="短"),
        _insight(confidence="low"),
    ]
    accepted, rejected = qf.filter(items)
    assert len(accepted) == 1
    assert len(rejected) == 2
    assert rejected[0]["reject_reason"] == "insight text too short"
    assert rejected[1]["reject_reason"] == "confidence below threshold"


def test_filter_empty():
    qf = QualityFilter()
    accepted, rejected = qf.filter([])
    assert accepted == []
    assert rejected == []


# ---------------------------------------------------------------------------
# compute_fill_rates
# ---------------------------------------------------------------------------

def test_compute_fill_rates_from_insight_count():
    dims = {
        "layers": {
            "1": {"latest_insights": [{}, {}]},        # 2 insights → 20
            "2": {"latest_insights": [{}] * 10},       # 10 insights → 100
            "3": {"latest_insights": [{}] * 15},       # 15 insights → 100 (capped)
        }
    }
    rates = compute_fill_rates(dims)
    assert rates["1"] == 20
    assert rates["2"] == 100
    assert rates["3"] == 100


def test_compute_fill_rates_explicit_override():
    dims = {
        "layers": {
            "1": {"latest_insights": [{}, {}], "fill_rate": 50},
        }
    }
    rates = compute_fill_rates(dims)
    assert rates["1"] == 50  # explicit value preserved


def test_compute_fill_rates_empty():
    rates = compute_fill_rates({"layers": {}})
    assert rates == {}


# ---------------------------------------------------------------------------
# public_projection
# ---------------------------------------------------------------------------

def test_public_projection_strips_insights():
    dims = {
        "version": "2.0",
        "layers": {
            "1": {
                "name": "Personality",
                "fill_rate": 35,
                "status": "partial",
                "latest_insights": [
                    {"insight": "secret text", "evidence": "secret evidence"}
                ],
            }
        }
    }
    pub = public_projection(dims)
    assert "latest_insights" not in pub["layers"]["1"]
    assert pub["layers"]["1"]["insight_count"] == 1
    assert pub["layers"]["1"]["fill_rate"] == 35
    assert pub["layers"]["1"]["status"] == "partial"


def test_public_projection_preserves_history():
    dims = {
        "version": "2.0",
        "layers": {},
        "history": [{"date": "2026-07-01", "total_insights": 10}],
    }
    pub = public_projection(dims)
    assert "history" in pub
    assert pub["history"][0]["total_insights"] == 10


def test_public_projection_empty_layer():
    dims = {"version": "2.0", "layers": {"1": {"name": "Test", "fill_rate": 0, "status": "empty"}}}
    pub = public_projection(dims)
    assert pub["layers"]["1"]["insight_count"] == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
