"""Extraction front-ends for Digital Twin sources."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .adapters.hermes import HermesMemoryReader, HermesSessionReader, HermesSession, format_session_for_llm
from .config import DTConfig


class HermesMemoryExtractor:
    """Extract Hermes sessions into an LLM-ready text bundle."""

    def __init__(self, config: DTConfig):
        self.config = config
        self.reader = HermesSessionReader(config.hermes_state_db)
        self.memory = HermesMemoryReader(config.dimensions_path)

    def last_extraction_time(self) -> datetime:
        return self.memory.last_extraction_time()

    def fetch_sessions(self, since: datetime | None = None) -> list[HermesSession]:
        since = since or self.last_extraction_time()
        return self.reader.hydrated_sessions_since(
            since,
            min_user_messages=self.config.min_user_messages,
            max_messages=self.config.max_messages_per_session,
        )

    def format_sessions(self, sessions: list[HermesSession]) -> str:
        if not sessions:
            return "NO_MEANINGFUL_SESSIONS"
        total_msgs = sum(len(s.messages) for s in sessions)
        total_users = sum(1 for s in sessions for m in s.messages if m.role == "user")
        total_tools = sum(1 for s in sessions for m in s.messages if m.role == "tool")
        parts = [
            f"SESSION_COUNT={len(sessions)}",
            f"TOTAL_MESSAGES={total_msgs} (user={total_users}, tool={total_tools})",
            "---",
        ]
        for session in sessions:
            parts.append(format_session_for_llm(session))
            parts.append("\n" + "=" * 60 + "\n")
        return "\n".join(parts)

    def extract_text(self, since: datetime | None = None) -> str:
        return self.format_sessions(self.fetch_sessions(since))
