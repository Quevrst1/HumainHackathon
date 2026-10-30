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


def finance_review(events: EventLog, department: str, budget_sar: int, previous_sar: int | None = None) -> dict:
    """Simulated budget check (not built yet), re-run whenever the budget changes.
    Edge case: Finance can't confirm its own budget (segregation of duties), so its own requests go to the General Manager."""
    amount = f"SAR {budget_sar:,}" if previous_sar is None else f"changed from SAR {previous_sar:,} to SAR {budget_sar:,}"
    if department == "Finance":
        review = {"step": "finance", "status": "escalated", "simulated": True, "budget_sar": budget_sar,
                  "note": f"Budget {amount}: Finance raised this request, so it can't confirm its own budget; "
                          "sent to the General Manager"}
    else:
        review = {"step": "finance", "status": "approved", "simulated": True, "budget_sar": budget_sar,
                  "note": f"Budget {amount}: confirmed"}
    events.emit("finance", "review", f"{review['note']} (simulated)", review)
    return review


def legal_review(events: EventLog) -> dict:
    """Simulated contract-terms review (not built yet): always approves."""
    review = {"step": "legal", "status": "approved", "note": "Contract terms approved", "simulated": True}
    events.emit("legal", "review", f"{review['note']} (simulated)", review)
    return review


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
        self.department = department
        self.budget_sar = budget_sar
        self.out_dir = self.out_root / "ui" / datetime.now().strftime("%Y%m%d-%H%M%S")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.events.add_listener(jsonl_listener(self.out_dir / "events.jsonl"))
        self.requester = UIRequester(Message(form_message(department, need, budget_sar), list(attachments)))
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            reviews = []

            def finance_checks(event):
                # Finance checks the budget right after the request, and again whenever the agent settles on a new one
                if event.stage == "request":
                    reviews.append(finance_review(self.events, self.department, self.budget_sar))
                elif event.tool == "purchase_route" and "budget_sar" in event.data:
                    confirmed = reviews[-1]["budget_sar"] if reviews else None
                    if event.data["budget_sar"] != confirmed:
                        reviews.append(finance_review(self.events, self.department, event.data["budget_sar"], confirmed))

            self.events.add_listener(finance_checks)
            self.package = run_agent(self.llm, self.requester, self.events, load_facts(), load_template(),
                                     date.today(), f"SAHAB-{self.out_dir.name}")
            if self.package["stopped_reason"] == "finished":
                reviews.append(legal_review(self.events))
            self.package["reviews"] = reviews
            save_package(self.out_dir, self.package)
            if self.package["tender"]:
                self.events.emit("generation", "generate", "Tender and PDF generated", {"folder": str(self.out_dir)})
        except Exception as e:   # surface the failure in the UI instead of dying silently
            self.error = str(e)
        self.done = True

    def pending_question(self) -> str | None:
        return self.requester.question if self.requester else None

    def answer(self, text: str, attachments: list[Path] = ()):
        self.requester._answers.put(Message(text, list(attachments)))

    def chat(self) -> list[dict]:
        return list(self.requester.chat) if self.requester else []
