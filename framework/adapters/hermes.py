"""Hermes state.db readers for Digital Twin extraction."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import sqlite3
from typing import Any, Iterable


@dataclass
class HermesMessage:
    role: str
    content: str
    timestamp: float | None = None
    token_count: int | None = None
    tool_name: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    reasoning_preview: str | None = None


@dataclass
class HermesSession:
    id: str
    title: str
    source: str | None
    model: str | None
    started_at: float | None
    ended_at: float | None
    message_count: int | None
    tool_call_count: int | None
    estimated_cost_usd: float | None
    messages: list[HermesMessage] = field(default_factory=list)


class HermesSessionReader:
    """Read Hermes sessions and messages from state.db without modifying it."""

    def __init__(self, state_db: str | Path):
        self.state_db = Path(state_db).expanduser()

    def _connect(self) -> sqlite3.Connection:
        if not self.state_db.exists():
            raise FileNotFoundError(f"Hermes state DB not found: {self.state_db}")
        conn = sqlite3.connect(str(self.state_db))
        conn.row_factory = sqlite3.Row
        return conn

    def sessions_since(self, since_dt: datetime) -> list[HermesSession]:
        since_ts = since_dt.timestamp()
        query = """
            SELECT DISTINCT s.id, s.title, s.source, s.model,
                   s.started_at, s.ended_at, s.message_count, s.tool_call_count,
                   s.estimated_cost_usd
            FROM sessions s
            JOIN messages m ON m.session_id = s.id
            WHERE m.timestamp > ?
            ORDER BY s.started_at ASC
        """
        with self._connect() as conn:
            rows = conn.execute(query, (since_ts,)).fetchall()
        return [
            HermesSession(
                id=row["id"],
                title=row["title"] or "(untitled)",
                source=row["source"],
                model=row["model"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                message_count=row["message_count"],
                tool_call_count=row["tool_call_count"],
                estimated_cost_usd=row["estimated_cost_usd"],
            )
            for row in rows
        ]

    def messages_for_session(self, session_id: str, limit: int = 500) -> list[HermesMessage]:
        query = """
            SELECT role, content, tool_calls, tool_name,
                   reasoning_content, timestamp, token_count
            FROM messages
            WHERE session_id = ?
              AND role IN ('user', 'assistant', 'tool')
              AND content IS NOT NULL
              AND length(content) > 10
            ORDER BY timestamp ASC
            LIMIT ?
        """
        messages: list[HermesMessage] = []
        with self._connect() as conn:
            rows = conn.execute(query, (session_id, limit)).fetchall()
        for row in rows:
            calls: list[dict[str, Any]] = []
            if row["tool_calls"]:
                try:
                    raw_calls = json.loads(row["tool_calls"])
                    for call in raw_calls:
                        fn = call.get("function", {}) if isinstance(call, dict) else {}
                        calls.append({
                            "name": fn.get("name") or call.get("name", "?"),
                            "args": str(fn.get("arguments") or call.get("arguments", ""))[:200],
                        })
                except Exception:
                    calls = []
            reasoning = row["reasoning_content"] or ""
            messages.append(HermesMessage(
                role=row["role"],
                content=row["content"],
                timestamp=row["timestamp"],
                token_count=row["token_count"],
                tool_name=row["tool_name"],
                tool_calls=calls,
                reasoning_preview=reasoning[:300] if len(reasoning) > 50 else None,
            ))
        return messages

    def hydrated_sessions_since(self, since_dt: datetime, *, min_user_messages: int = 5, max_messages: int = 500) -> list[HermesSession]:
        sessions = self.sessions_since(since_dt)
        hydrated: list[HermesSession] = []
        for session in sessions:
            session.messages = self.messages_for_session(session.id, max_messages)
            user_count = sum(1 for m in session.messages if m.role == "user")
            if user_count >= min_user_messages:
                hydrated.append(session)
        return hydrated


class HermesMemoryReader:
    """Read last extraction timestamp and existing dimension memory files."""

    def __init__(self, dimensions_path: str | Path):
        self.dimensions_path = Path(dimensions_path).expanduser()

    def last_extraction_time(self) -> datetime:
        try:
            data = json.loads(self.dimensions_path.read_text(encoding="utf-8"))
            last = data.get("last_extraction")
            if last:
                return datetime.fromisoformat(last)
        except Exception:
            pass
        return datetime.now(timezone.utc) - timedelta(hours=24)

    def load_dimensions(self) -> dict[str, Any]:
        if not self.dimensions_path.exists():
            return {}
        return json.loads(self.dimensions_path.read_text(encoding="utf-8"))


def format_session_for_llm(session: HermesSession) -> str:
    lines: list[str] = []
    lines.append(f"## Session: {session.title}")
    lines.append(
        f"   model={session.model} | source={session.source} | "
        f"msgs={session.message_count} | tools={session.tool_call_count} | "
        f"cost=${session.estimated_cost_usd or 0:.4f}"
    )
    lines.append("")
    for msg in session.messages:
        if msg.role == "user":
            lines.extend(["### USER", msg.content])
        elif msg.role == "assistant":
            if msg.reasoning_preview:
                lines.append(f"### ASSISTANT [reasoning: {msg.reasoning_preview[:100]}...]")
            elif msg.tool_calls:
                lines.append("### ASSISTANT [tools: " + ", ".join(t["name"] for t in msg.tool_calls) + "]")
            else:
                lines.append("### ASSISTANT")
            lines.append(msg.content[:2000])
        elif msg.role == "tool":
            preview = msg.content[:500].replace("\n", " ")
            lines.append(f"### TOOL [{msg.tool_name or '?'}]: {preview}")
        lines.append("")
    return "\n".join(lines)
