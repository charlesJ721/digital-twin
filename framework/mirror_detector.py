"""
mirror_detector.py — Agent 行为自检器。

检测两种Agent行为偏差：
- Mirror（镜像）：Agent 不自觉地复述了用户的措辞
- Loop（循环）：Agent 在重复自己上一轮的输出

纯 Python 标准库，字符 bigram + Jaccard 相似度。
逐字精确匹配中文——不受分词影响，不受 LLM 模型影响。

Usage:
    from mirror_detector import MirrorDetector
    md = MirrorDetector()
    result = md.check(agent_response, user_message)
    # result.mirror, result.loop, result.warning

阈值参考：
    mirror_threshold=0.25  # 超过25% bigram重叠→镜像
    loop_threshold=0.40    # 超过40% bigram重叠→循环
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CheckResult:
    mirror: bool = False
    mirror_score: float = 0.0
    loop: bool = False
    loop_score: float = 0.0
    style_note: Optional[str] = None
    warning: Optional[str] = None

    def __bool__(self) -> bool:
        return self.mirror or self.loop


def _bigrams(text: str) -> set:
    """字符级 bigram——不对中文分词，逐字滑动窗口。"""
    return {text[i:i+2] for i in range(len(text) - 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class MirrorDetector:
    mirror_threshold: float = 0.25
    loop_threshold: float = 0.40
    short_response_threshold: int = 20   # 短回复判定阈值（字符）
    short_response_ratio_warn: float = 0.6  # 短回复占比超过此值→警告
    history: List[str] = field(default_factory=list)
    max_history: int = 5

    def check(self, agent_response: str, user_message: str) -> CheckResult:
        result = CheckResult()

        # ── Mirror：Agent ↔ 用户 ──
        if agent_response and user_message:
            result.mirror_score = _jaccard(
                _bigrams(agent_response), _bigrams(user_message)
            )
            result.mirror = result.mirror_score > self.mirror_threshold

        # ── Loop：Agent ↔ 自己上一轮 ──
        if len(self.history) >= 1 and agent_response:
            result.loop_score = _jaccard(
                _bigrams(agent_response), _bigrams(self.history[-1])
            )
            result.loop = result.loop_score > self.loop_threshold

        # ── Style check：短回复占比 ──
        self.history.append(agent_response)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        short_count = sum(
            1 for r in self.history if len(r) < self.short_response_threshold
        )
        if len(self.history) >= 3 and short_count / len(self.history) > self.short_response_ratio_warn:
            result.style_note = f"high short-response ratio ({short_count}/{len(self.history)})"

        # ── Warning 生成 ──
        parts = []
        if result.mirror:
            parts.append(f"mirror({result.mirror_score:.2f})")
        if result.loop:
            parts.append(f"loop({result.loop_score:.2f})")
        if result.style_note:
            parts.append(result.style_note)
        if parts:
            result.warning = " · ".join(parts)

        return result

    def reset(self):
        self.history.clear()
