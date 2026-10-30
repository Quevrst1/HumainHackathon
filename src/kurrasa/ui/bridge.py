import queue
import threading
from datetime import date, datetime
from pathlib import Path

from kurrasa.agents.kurrasa import run_agent
from kurrasa.agents.session import Message
from kurrasa.pipeline.run import save_package
from kurrasa.services.company import load_facts, load_template
from kurrasa.services.events import EventLog, jsonl_listener


def form_message(department: str, need: str, budget_sar: int) -> str:
    return f"Department: {department}\nRequest: {need}\nBudget: SAR {budget_sar:,}"


def simulated_reviews(events: EventLog) -> list[dict]:
    """Placeholder Finance and Legal sign-offs: always approve, clearly marked as simulated (not built yet)."""
    reviews = [
        {"step": "finance", "status": "approved", "note": "Budget confirmed", "simulated": True},
        {"step": "legal", "status": "approved", "note": "Contract terms approved", "simulated": True},
    ]
    for r in reviews:
        events.emit(r["step"], "review", f"{r['note']} (simulated)", r)
    return reviews


class UIRequester:
    """The person using the UI: the agent's questions wait here until they answer."""

    def __init__(self, opening: Message):
        self._opening = opening
        self._answers: queue.Queue[Message] = queue.Queue()
        self.question: str | None = None
        self.chat = [{"role": "requester", "text": opening.text}]

    def opening(self) -> Message:
        return self._opening

    def reply(self, question: str) -> Message:
        self.chat.append({"role": "agent", "text": question})
        self.question = question
        answer = self._answers.get()   # blocks the agent thread until the person answers
        self.question = None
        self.chat.append({"role": "requester", "text": answer.text})
        return answer


class AgentRunner:
    """Runs one Kurrasa session in a background thread so a UI can stay responsive."""

    def __init__(self, llm, out_root: Path = Path("results")):
        self.llm = llm
        self.out_root = out_root
        self.events = EventLog()
        self.requester: UIRequester | None = None
        self.package: dict | None = None
        self.error: str | None = None
        self.done = False
        self.out_dir: Path | None = None

    def start(self, department: str, need: str, budget_sar: int, attachments: list[Path] = ()):
        self.out_dir = self.out_root / "ui" / datetime.now().strftime("%Y%m%d-%H%M%S")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.events.add_listener(jsonl_listener(self.out_dir / "events.jsonl"))
        self.requester = UIRequester(Message(form_message(department, need, budget_sar), list(attachments)))
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self.package = run_agent(self.llm, self.requester, self.events, load_facts(), load_template(),
                                     date.today(), f"SAHAB-{self.out_dir.name}")
            if self.package["stopped_reason"] == "finished":
                self.package["reviews"] = simulated_reviews(self.events)
            save_package(self.out_dir, self.package)
        except Exception as e:   # surface the failure in the UI instead of dying silently
            self.error = str(e)
        self.done = True

    def pending_question(self) -> str | None:
        return self.requester.question if self.requester else None

    def answer(self, text: str, attachments: list[Path] = ()):
        self.requester._answers.put(Message(text, list(attachments)))

    def chat(self) -> list[dict]:
        return list(self.requester.chat) if self.requester else []
