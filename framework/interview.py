"""Cold-start interviewer prompts for bootstrapping a new DT user."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InterviewQuestion:
    layer: str
    prompt: str


class ColdStartInterviewer:
    QUESTIONS = [
        InterviewQuestion("1", "What reliably motivates you, and what do you avoid even when it is rewarded?"),
        InterviewQuestion("2", "How do you make hard decisions when evidence is incomplete?"),
        InterviewQuestion("3", "Which values do you protect even when they cost convenience or status?"),
        InterviewQuestion("4", "What recurring behavior pattern appears under stress or high energy?"),
        InterviewQuestion("5", "What knowledge domains shape how you interpret the world?"),
        InterviewQuestion("6", "How do you decide whom to trust, collaborate with, or keep at distance?"),
        InterviewQuestion("7", "What story do you tell about who you are becoming?"),
    ]

    def questions(self) -> list[InterviewQuestion]:
        return list(self.QUESTIONS)

    def markdown(self) -> str:
        lines = ["# Digital Twin Cold-Start Interview", ""]
        for q in self.QUESTIONS:
            lines.append(f"## L{q.layer}")
            lines.append(q.prompt)
            lines.append("")
        return "\n".join(lines)
