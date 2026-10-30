from kurrasa.agents.session import Message, Session
from kurrasa.agents.tools import build_tools
from kurrasa.services.company import AGENT_BLANKS, load_facts
from kurrasa.services.events import EventLog


class StubRequester:
    def __init__(self, replies):
        self.replies = list(replies)
        self.questions = []

    def reply(self, question):
        self.questions.append(question)
        return self.replies.pop(0) if self.replies else Message(text="ok")


def make(replies=()):
    session, events, requester = Session(), EventLog(), StubRequester(replies)
    tools = {t.name: t for t in build_tools(session, requester, events, load_facts())}
    return session, events, requester, tools


def test_question_cap():
    session, _, requester, tools = make()
    for _ in range(10):
        tools["ask_requester"].invoke({"question": "q"})
    answer = tools["ask_requester"].invoke({"question": "one more"})
    assert "Question limit (10) reached" in answer
    assert len(requester.questions) == 10 and session.questions_asked == 10


def test_done_ends_interview():
    session, _, requester, tools = make([Message(text="ok", done=True)])
    first = tools["ask_requester"].invoke({"question": "q"})
    assert "ended the interview" in first and session.interview_ended
    assert tools["ask_requester"].invoke({"question": "q2"}) == "The requester has ended the interview."
    assert len(requester.questions) == 1


def test_purchase_route_rejects_bad_budget():
    session, _, _, tools = make()
    result = tools["purchase_route"].invoke({"budget_sar": 0})
    assert result.startswith("Invalid budget") and session.route is None
    assert "limited competition" in tools["purchase_route"].invoke({"budget_sar": 900_000})
    assert session.route == {"method": "limited competition", "approver": "General Manager"}


def test_issue_ids_and_resolve():
    session, _, _, tools = make()
    assert tools["raise_issue"].invoke({"description": "a"}) == "Issue 1 recorded"
    assert tools["raise_issue"].invoke({"description": "b"}) == "Issue 2 recorded"
    tools["resolve_issue"].invoke({"issue_id": 2, "resolution": "fixed"})
    assert session.issues[1]["status"] == "resolved" and session.issues[1]["resolution"] == "fixed"
    assert session.issues[0]["status"] == "open"
    assert "No issue" in tools["resolve_issue"].invoke({"issue_id": 9, "resolution": "x"})


def test_write_section_validates_name():
    session, _, _, tools = make()
    assert "SCOPE" in tools["write_section"].invoke({"name": "FOO", "text": "x"})
    assert session.sections == {}


def test_finish_requires_all_sections():
    session, _, _, tools = make()
    assert tools["finish"].invoke({}).startswith("Cannot finish, missing sections:")
    assert not session.finished
    for b in AGENT_BLANKS:
        tools["write_section"].invoke({"name": b, "text": "نص"})
    tools["finish"].invoke({})
    assert session.finished


def test_every_tool_emits_one_event_with_stage():
    _, events, _, tools = make()
    calls = [
        ("ask_requester", {"question": "q"}, "interview"),
        ("record_requirement", {"name": "users", "value": "120"}, "interview"),
        ("purchase_route", {"budget_sar": 50_000}, "checks"),
        ("raise_issue", {"description": "x"}, "checks"),
        ("resolve_issue", {"issue_id": 1, "resolution": "y"}, "checks"),
        ("write_section", {"name": "TITLE", "text": "t"}, "draft"),
        ("finish", {}, "package"),
    ]
    for name, args, stage in calls:
        before = len(events.events)
        tools[name].invoke(args)
        assert len(events.events) == before + 1
        assert events.events[-1].tool == name and events.events[-1].stage == stage
