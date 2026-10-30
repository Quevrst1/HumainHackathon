import json

from langchain_core.tools import BaseTool, tool

from kurrasa.config import MAX_QUESTIONS
from kurrasa.services.company import AGENT_BLANKS, purchase_route as route_for


def build_tools(session, requester, events, facts) -> list[BaseTool]:
    """The agent's tools. They only act or store; Gemini does the thinking. Tools never raise."""

    @tool
    def ask_requester(question: str) -> str:
        """Ask the requesting employee a question and return their answer."""
        if session.interview_ended:
            events.emit("interview", "ask_requester", "Interview already ended by the requester")
            return "The requester has ended the interview."
        if session.questions_asked >= MAX_QUESTIONS:
            events.emit("interview", "ask_requester", "Question limit reached")
            return f"Question limit ({MAX_QUESTIONS}) reached. Finish now and record remaining gaps with raise_issue."

        session.questions_asked += 1
        reply = requester.reply(question)
        session.transcript.append({"role": "agent", "text": question, "attachments": []})
        session.transcript.append({"role": "requester", "text": reply.text,
                                   "attachments": [str(p) for p in reply.attachments]})
        session.pending_attachments += reply.attachments
        events.emit("interview", "ask_requester", f"Asked: {question}", {"question": question, "answer": reply.text})

        if reply.done:
            session.interview_ended = True
            return reply.text + " [The requester ended the interview. Do not ask more questions; finish with what you have.]"
        return reply.text

    @tool
    def record_requirement(name: str, value: str) -> str:
        """Save a requirement you have learned, e.g. name='users', value='120'."""
        session.requirements[name] = value
        events.emit("interview", "record_requirement", f"Noted {name}: {value}", {"name": name, "value": value})
        return "saved"

    @tool
    def purchase_route(budget_sar: int) -> str:
        """Return the purchasing method and approver for a budget in SAR, from the company rules."""
        try:
            session.route = route_for(budget_sar, facts)
        except ValueError:
            events.emit("checks", "purchase_route", "Invalid budget given")
            return "Invalid budget: ask the requester for a positive amount in SAR."
        events.emit("checks", "purchase_route",
                    f"{session.route['method']}, approved by {session.route['approver']}",
                    {**session.route, "budget_sar": budget_sar})
        return json.dumps(session.route)

    @tool
    def raise_issue(description: str) -> str:
        """Record a problem with the request. Returns the issue id."""
        issue = {"id": len(session.issues) + 1, "description": description, "status": "open", "resolution": None}
        session.issues.append(issue)
        events.emit("checks", "raise_issue", f"Issue {issue['id']}: {description}", issue)
        return f"Issue {issue['id']} recorded"

    @tool
    def resolve_issue(issue_id: int, resolution: str) -> str:
        """Mark an issue as resolved and say how it was resolved."""
        issue = next((i for i in session.issues if i["id"] == issue_id), None)
        if issue is None:
            events.emit("checks", "resolve_issue", f"Unknown issue {issue_id}")
            return f"No issue with id {issue_id}."
        issue.update(status="resolved", resolution=resolution)
        events.emit("checks", "resolve_issue", f"Issue {issue_id} resolved: {resolution}", issue)
        return f"Issue {issue_id} resolved"

    @tool
    def write_section(name: str, text: str) -> str:
        """Fill one blank of the Arabic tender template."""
        if name not in AGENT_BLANKS:
            events.emit("draft", "write_section", f"Unknown section {name}")
            return f"Unknown section {name}. Valid sections: {', '.join(AGENT_BLANKS)}"
        session.sections[name] = text
        events.emit("draft", "write_section", f"Wrote {name}", {"name": name})
        return "saved"

    @tool
    def finish() -> str:
        """Finish once every section is written. Hands over the tender package."""
        missing = [b for b in AGENT_BLANKS if b not in session.sections]
        if missing:
            events.emit("package", "finish", "Tried to finish with missing sections", {"missing": missing})
            return f"Cannot finish, missing sections: {', '.join(missing)}"
        session.finished = True
        events.emit("package", "finish", "Tender package ready")
        return "done"

    return [ask_requester, record_requirement, purchase_route, raise_issue, resolve_issue, write_section, finish]
