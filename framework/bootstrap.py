"""Bootstrap Persona Profile from existing data sources.

Path B (Agent memory import): reads Hermes state.db, extracts recent
sessions, and generates an initial Digital Twin profile via LLM analysis.

Path A (interactive interview): reserved for future implementation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import DTConfig, load_config
from .extractors import HermesMemoryExtractor
from .pipeline import DigitalTwinPipeline
from .extract_insights import build_prompt, extract_insights as _extract_llm


def _extract_text_for_period(config: DTConfig, days: int) -> str:
    """Extract sessions from the last `days` days, bypassing last_extraction_time."""
    extractor = HermesMemoryExtractor(config)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sessions = extractor.reader.hydrated_sessions_since(
        since,
        min_user_messages=config.min_user_messages,
        max_messages=config.max_messages_per_session,
    )
    return extractor.format_sessions(sessions)


def bootstrap_from_hermes(
    config_path: str | Path = "config.yaml",
    *,
    days: int = 90,
    call_llm: bool = False,
    model: str = "deepseek-chat",
    api_key: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Generate an initial Persona Profile from Hermes session history.

    Args:
        config_path: Path to config.yaml.
        days: How many days of session history to analyze.
        call_llm: If True, call LLM API to generate insights.
                  If False, output the prompt for manual analysis.
        model: LLM model ID (only used when call_llm=True).
        api_key: DeepSeek/OpenAI-compatible API key.
        force: Overwrite existing dimensions.json.

    Returns:
        Dict with keys: mode, session_count, total_messages, prompt_chars,
        insights (if call_llm), dimensions_path, public_dimensions_path.
    """
    from .cli import init_user

    cfg = load_config(config_path)

    # Initialize user data directory if needed
    if not cfg.dimensions_path.exists() or force:
        init_user(str(config_path), force=force)

    # Extract sessions
    text = _extract_text_for_period(cfg, days)

    if text == "NO_MEANINGFUL_SESSIONS" or not text.strip():
        return {
            "mode": "empty",
            "session_count": 0,
            "total_messages": 0,
            "message": "No meaningful sessions found in the specified period.",
        }

    # Count sessions from the formatted text
    session_count = 0
    total_msgs = 0
    for line in text.split("\n"):
        if line.startswith("SESSION_COUNT="):
            session_count = int(line.split("=")[1])
        if line.startswith("TOTAL_MESSAGES="):
            total_msgs = int(line.split("=")[1].split()[0])

    if call_llm:
        result = _extract_llm(text, model=model, api_key=api_key, validate=True)
        insights = result.get("insights", [])

        # Write to dimensions
        pipeline = DigitalTwinPipeline(cfg)
        merge_result = pipeline.merge_insights(insights)

        return {
            "mode": "llm",
            "session_count": session_count,
            "total_messages": total_msgs,
            "prompt_chars": result.get("prompt_chars", 0),
            "insights_generated": result.get("raw_count", 0),
            "insights_valid": result.get("valid_count", 0),
            "insights_rejected": result.get("rejected_count", 0),
            "insights_merged": merge_result.get("merged", 0),
            "contradictions": merge_result.get("contradictions", []),
            "dimensions_path": str(cfg.dimensions_path),
            "public_dimensions_path": str(cfg.public_dimensions_path),
        }

    # Prompt-only mode
    prompt = build_prompt(text)
    return {
        "mode": "prompt",
        "session_count": session_count,
        "total_messages": total_msgs,
        "prompt_chars": len(prompt),
        "prompt": prompt,
        "hint": "Feed this prompt to an LLM. Save the JSON output and run: "
                "python3 -m framework.pipeline --config config.yaml --merge-json <output.json>",
    }
