"""Insight extraction from LLM-ready session text.

Takes the output of extractors.extract_text() and produces structured
insight JSON aligned with INTEGRATION.md schema. Provides:
- Prompt generation (from template)
- Schema validation
- Optional LLM API call (DeepSeek/OpenAI-compatible)
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_insights.txt"

# Required fields per insight (from 7-layer-schema.yaml + INTEGRATION.md)
REQUIRED_FIELDS = ["date", "dimension", "insight", "confidence", "evidence"]
VALID_CONFIDENCE = {"high", "medium", "low"}
MAX_INSIGHT_CHARS = 2000


def load_prompt_template() -> str:
    """Load the extract_insights prompt template."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_prompt(extraction_text: str, template: str | None = None) -> str:
    """Build a complete LLM prompt by filling the template with session text."""
    tpl = template or load_prompt_template()
    return tpl.replace("{extraction_text}", extraction_text)


def validate_insight(insight: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate a single insight dict against the DT schema.

    Returns (is_valid, error_reason).
    """
    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in insight or not str(insight.get(field, "")).strip():
            return False, f"missing or empty required field: {field}"

    # Confidence must be valid
    confidence = str(insight.get("confidence", "")).lower()
    if confidence not in VALID_CONFIDENCE:
        return False, f"invalid confidence: {confidence}"

    # Insight text length
    text = str(insight.get("insight", ""))
    if len(text) > MAX_INSIGHT_CHARS:
        return False, f"insight text too long ({len(text)} > {MAX_INSIGHT_CHARS})"

    # Date format
    date_val = str(insight.get("date", ""))
    try:
        date.fromisoformat(date_val[:10])
    except (ValueError, TypeError):
        return False, f"invalid date format: {date_val}"

    return True, None


def validate_insights(insights: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate a list of insights, returning (valid, rejected)."""
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in insights:
        ok, reason = validate_insight(item)
        if ok:
            valid.append(item)
        else:
            item["reject_reason"] = reason
            rejected.append(item)
    return valid, rejected


def parse_llm_output(raw_output: str) -> list[dict[str, Any]]:
    """Parse LLM output into a list of insight dicts.

    Handles:
    - Pure JSON: {"insights": [...]}
    - JSON array: [...]
    - Markdown-fenced JSON: ```json ... ```
    - Text with embedded JSON (extracts first valid JSON object/array)
    """
    text = raw_output.strip()

    # Try markdown code fence first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Try direct JSON parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object/array boundaries
        for pattern in [r"\{[\s\S]*\"insights\"[\s\S]*\}", r"\[[\s\S]*\{[\s\S]*\}[^\]]*\]"]:
            match = re.search(pattern, text)
            if match:
                try:
                    data = json.loads(match.group(0))
                    break
                except json.JSONDecodeError:
                    continue
        else:
            raise ValueError(f"Could not parse JSON from LLM output. First 500 chars: {raw_output[:500]}")

    if isinstance(data, dict):
        return data.get("insights", [])
    if isinstance(data, list):
        return data
    return []


def call_llm(
    prompt: str,
    *,
    api_key: str | None = None,
    api_base: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Call an OpenAI-compatible LLM API with the given prompt.

    Returns the raw response text.
    """
    key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError("No API key provided. Set DEEPSEEK_API_KEY or pass api_key=.")

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")

    req = urlrequest.Request(
        f"{api_base.rstrip('/')}/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    with urlrequest.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"LLM returned empty response: {json.dumps(body, ensure_ascii=False)[:500]}")
    return content


def extract_insights(
    extraction_text: str,
    *,
    api_key: str | None = None,
    api_base: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-chat",
    prompt_template: str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Full pipeline: generate prompt → call LLM → parse → validate.

    Returns:
        {
            "insights": [...valid insights...],
            "rejected": [...rejected insights with reasons...],
            "raw_count": N,
            "valid_count": N,
            "rejected_count": N,
            "prompt_chars": N,
            "model": str,
            "extracted_at": "ISO timestamp",
        }
    """
    prompt = build_prompt(extraction_text, prompt_template)
    raw = call_llm(prompt, api_key=api_key, api_base=api_base, model=model)
    parsed = parse_llm_output(raw)

    if validate:
        valid, rejected = validate_insights(parsed)
    else:
        valid, rejected = parsed, []

    return {
        "insights": valid,
        "rejected": rejected,
        "raw_count": len(parsed),
        "valid_count": len(valid),
        "rejected_count": len(rejected),
        "prompt_chars": len(prompt),
        "model": model,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
