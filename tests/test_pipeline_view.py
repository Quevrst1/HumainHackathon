from kurrasa.services.events import Event
from kurrasa.ui.pipeline_view import pipeline_state


def ev(stage, summary="x", tool="tool", data=None):
    return Event("2026-10-30T12:00:00", stage, tool, summary, data or {})


def states(nodes):
    return {n["node"]: n["state"] for n in nodes}


def test_waiting_for_the_department():
    events = [ev("request"), ev("finance", data={"status": "approved"}), ev("interview", "Asked: users?", "ask_requester")]
    s = states(pipeline_state(events, "IT & Security", waiting=True, finished=False))
    assert s == {"department": "waiting", "finance": "done", "procurement": "active",
                 "legal": "pending", "generation": "pending", "done": "pending"}


def test_procurement_working_then_legal():
    events = [ev("request"), ev("finance", data={"status": "approved"}), ev("checks"), ev("draft"), ev("legal")]
    s = states(pipeline_state(events, "Sales", waiting=False, finished=False))
    assert s["procurement"] == "done" and s["legal"] == "active" and s["generation"] == "pending"


def test_finished_and_finance_escalation():
    events = [ev("request"), ev("finance", data={"status": "escalated"}), ev("draft"), ev("legal"), ev("generation")]
    nodes = pipeline_state(events, "Finance", waiting=False, finished=True)
    s = states(nodes)
    assert s["finance"] == "escalated" and s["done"] == "done" and s["generation"] == "done"
    assert nodes[0]["label"] == "Finance"   # the department node is named after the requesting department


def test_counts_questions_to_the_department():
    events = [ev("request"), ev("finance", data={"status": "approved"}),
              ev("interview", tool="ask_requester"), ev("checks"), ev("interview", tool="ask_requester")]
    procurement = next(n for n in pipeline_state(events, "Sales", False, False) if n["node"] == "procurement")
    assert "2 questions" in procurement["detail"]
