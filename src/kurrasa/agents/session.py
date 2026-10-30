from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Message:
    text: str
    attachments: list[Path] = field(default_factory=list)
    done: bool = False   # the requester ended the interview


@dataclass
class Session:
    """Everything the agent has learned and produced during one run."""
    requirements: dict = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    sections: dict = field(default_factory=dict)
    route: dict | None = None
    questions_asked: int = 0
    transcript: list[dict] = field(default_factory=list)
    pending_attachments: list[Path] = field(default_factory=list)
    interview_ended: bool = False
    finished: bool = False
