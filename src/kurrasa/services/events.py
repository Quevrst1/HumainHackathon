import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass
class Event:
    time: str
    stage: str
    tool: str
    summary: str
    data: dict = field(default_factory=dict)


class EventLog:
    """Collects what the agent does and passes each step to whoever is listening (terminal, file, UI)."""

    def __init__(self):
        self.events: list[Event] = []
        self.listeners: list[Callable[[Event], None]] = []

    def add_listener(self, fn: Callable[[Event], None]):
        self.listeners.append(fn)

    def emit(self, stage: str, tool: str, summary: str, data: dict | None = None) -> Event:
        event = Event(datetime.now(timezone.utc).isoformat(timespec="seconds"), stage, tool, summary, data or {})
        self.events.append(event)
        for fn in self.listeners:
            fn(event)
        return event


def print_listener(event: Event):
    print(f"[{event.stage:9}] {event.summary}")


def jsonl_listener(path: Path) -> Callable[[Event], None]:
    def write(event: Event):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
    return write
