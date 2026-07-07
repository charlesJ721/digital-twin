"""Unit tests for insight validation and LLM output parsing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.extract_insights import (
    validate_insight,
    validate_insights,
    parse_llm_output,
    build_prompt,
    load_prompt_template,
)


# ---------------------------------------------------------------------------
# validate_insight
# ---------------------------------------------------------------------------

def _valid():
    return {
        "date": "2026-07-07",
        "dimension": "决策风格",
        "insight": "用户在技术选型中优先考虑延展性",
        "confidence": "high",
        "evidence": "选这个方案是因为它以后能扩展",
    }


def test_validate_all_valid():
    ok, reason = validate_insight(_valid())
    assert ok
    assert reason is None


def test_validate_missing_date():
    ins = _valid()
    del ins["date"]
    ok, reason = validate_insight(ins)
    assert not ok
    assert "date" in reason


def test_validate_empty_date():
    ok, reason = validate_insight({**_valid(), "date": ""})
    assert not ok
    assert "date" in reason


def test_validate_missing_dimension():
    ins = _valid()
    del ins["dimension"]
    ok, reason = validate_insight(ins)
    assert not ok
    assert "dimension" in reason


def test_validate_missing_insight():
    ins = _valid()
    del ins["insight"]
    ok, reason = validate_insight(ins)
    assert not ok
    assert "insight" in reason


def test_validate_missing_confidence():
    ins = _valid()
    del ins["confidence"]
    ok, reason = validate_insight(ins)
    assert not ok
    assert "confidence" in reason


def test_validate_missing_evidence():
    ins = _valid()
    del ins["evidence"]
    ok, reason = validate_insight(ins)
    assert not ok
    assert "evidence" in reason


def test_validate_invalid_confidence():
    ok, reason = validate_insight({**_valid(), "confidence": "ultra"})
    assert not ok


def test_validate_bad_date():
    ok, reason = validate_insight({**_valid(), "date": "not-a-date"})
    assert not ok


def test_validate_too_long():
    ok, reason = validate_insight({**_valid(), "insight": "x" * 3000})
    assert not ok
    assert "long" in reason


# ---------------------------------------------------------------------------
# validate_insights (batch)
# ---------------------------------------------------------------------------

def test_validate_insights_batch():
    """low confidence passes schema validation (rejected later by QualityFilter)."""
    valid, rejected = validate_insights([
        _valid(),
        _valid(),
        {**_valid(), "confidence": "low"},       # schema-valid (low ∈ VALID_CONFIDENCE)
        {"date": "", "dimension": "", "insight": "", "confidence": "", "evidence": ""},  # all empty
    ])
    assert len(valid) == 3  # low confidence is schema-valid
    assert len(rejected) == 1  # only the all-empty one


# ---------------------------------------------------------------------------
# parse_llm_output
# ---------------------------------------------------------------------------

def test_parse_clean_json_object():
    raw = '{"insights": [{"date": "2026-07-07", "dimension": "x", "insight": "x", "confidence": "high", "evidence": "x"}]}'
    result = parse_llm_output(raw)
    assert len(result) == 1
    assert result[0]["dimension"] == "x"


def test_parse_json_array():
    raw = '[{"date": "2026-07-07", "dimension": "x", "insight": "x", "confidence": "high", "evidence": "x"}]'
    result = parse_llm_output(raw)
    assert len(result) == 1


def test_parse_code_fenced_json():
    raw = '```json\n{"insights": []}\n```'
    result = parse_llm_output(raw)
    assert result == []


def test_parse_empty_insights():
    raw = '{"insights": []}'
    result = parse_llm_output(raw)
    assert result == []


def test_parse_embedded_json():
    raw = 'Here is the result:\n{"insights": [{"date": "2026-07-07", "dimension": "x", "insight": "x", "confidence": "high", "evidence": "x"}]}\nEnd.'
    result = parse_llm_output(raw)
    assert len(result) == 1


def test_parse_garbage_raises():
    try:
        parse_llm_output("not json at all")
        assert False, "should have raised"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_fills_template():
    prompt = build_prompt("TEST_SESSION_TEXT_HERE")
    assert "TEST_SESSION_TEXT_HERE" in prompt
    assert "七层认知维度" in prompt
    assert "五道质量门" in prompt


def test_build_prompt_no_placeholder_left():
    prompt = build_prompt("text")
    assert "{extraction_text}" not in prompt


def test_load_prompt_template():
    tpl = load_prompt_template()
    assert len(tpl) > 500
    assert "{extraction_text}" in tpl


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
