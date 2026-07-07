"""Unit tests for dimension schema mapping.

Covers the three-tier mapping: arrow pattern → English keywords → Chinese hints.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from framework.schema import DimensionSchema, ZH_LAYER_HINTS

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "framework" / "schema" / "7-layer-schema.yaml"


def _schema():
    return DimensionSchema.from_file(SCHEMA_PATH)


# ---------------------------------------------------------------------------
# Arrow pattern (L1-L7, layer 1-7)
# ---------------------------------------------------------------------------

def test_arrow_L_digit():
    assert _schema().map_dimension("L2") == "2"
    assert _schema().map_dimension("L7") == "7"
    assert _schema().map_dimension("→ L4") == "4"


def test_arrow_layer_spelled():
    assert _schema().map_dimension("layer 3") == "3"
    assert _schema().map_dimension("Layer 1") == "1"


def test_arrow_case_insensitive():
    assert _schema().map_dimension("l5") == "5"


# ---------------------------------------------------------------------------
# English keywords (from schema.yaml)
# ---------------------------------------------------------------------------

def test_english_exact_keyword():
    assert _schema().map_dimension("personality") == "1"
    assert _schema().map_dimension("reasoning") == "2"
    assert _schema().map_dimension("values") == "3"
    assert _schema().map_dimension("behavior") == "4"
    assert _schema().map_dimension("knowledge") == "5"
    assert _schema().map_dimension("social") == "6"
    assert _schema().map_dimension("narrative") == "7"


def test_english_keyword_case_insensitive():
    assert _schema().map_dimension("Personality Trait") == "1"
    assert _schema().map_dimension("Cognitive Architecture") == "2"


# ---------------------------------------------------------------------------
# Chinese hints (ZH_LAYER_HINTS fallback)
# ---------------------------------------------------------------------------

def test_chinese_l1():
    assert _schema().map_dimension("人格") == "1"
    assert _schema().map_dimension("动机") == "1"
    assert _schema().map_dimension("核心驱动力") == "1"


def test_chinese_l2():
    assert _schema().map_dimension("推理风格") == "2"
    assert _schema().map_dimension("认知偏误") == "2"
    assert _schema().map_dimension("元认知") == "2"


def test_chinese_l3():
    assert _schema().map_dimension("价值观") == "3"
    assert _schema().map_dimension("伦理") == "3"


def test_chinese_l4():
    assert _schema().map_dimension("行为模式") == "4"
    assert _schema().map_dimension("防御机制") == "4"


def test_chinese_l5():
    assert _schema().map_dimension("知识结构") == "5"
    assert _schema().map_dimension("领域专长") == "5"


def test_chinese_l6():
    assert _schema().map_dimension("社会关系") == "6"
    assert _schema().map_dimension("信任建立") == "6"
    assert _schema().map_dimension("亲密关系") == "6"
    # "互动模式" is ambiguous: "互动"→L6 but "模式"→L4 matches first in iteration order


def test_chinese_l7():
    assert _schema().map_dimension("叙事自我") == "7"
    assert _schema().map_dimension("关键转折") == "7"


# ---------------------------------------------------------------------------
# Unknown / edge cases
# ---------------------------------------------------------------------------

def test_unknown_dimension():
    assert _schema().map_dimension("完全不存在的维度XYZ") is None
    assert _schema().map_dimension("") is None
    assert _schema().map_dimension("   ") is None


def test_compound_match():
    """A dimension containing keywords from multiple layers should match the first found."""
    result = _schema().map_dimension("人格与认知分析")  # "人格"=L1, "认知"=L2
    assert result in ("1", "2")  # implementation-defined order


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_all_seven_layers():
    s = _schema()
    assert set(s.layers.keys()) == {"1", "2", "3", "4", "5", "6", "7"}


def test_zh_hints_coverage():
    """Every layer must have at least one Chinese hint."""
    for lid in ("1", "2", "3", "4", "5", "6", "7"):
        assert lid in ZH_LAYER_HINTS
        assert len(ZH_LAYER_HINTS[lid]) > 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
