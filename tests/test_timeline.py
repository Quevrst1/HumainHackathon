from kurrasa.services.events import Event
from kurrasa.ui.timeline import build_timeline


def ev(stage, summary):
    return Event("2026-10-30T12:00:00", stage, "tool", summary)


def test_build_timeline_groups_steps_and_marks_going_back():
    events = [ev("request", "Request: laptops"), ev("interview", "Asked: specs?"), ev("interview", "Noted specs"),
              ev("checks", "Route: general competition"), ev("interview", "Asked: why Dell?"),
              ev("draft", "Wrote TITLE"), ev("draft", "Wrote SCOPE"), ev("package", "Tender package ready")]
    steps = build_timeline(events)
    assert [s["stage"] for s in steps] == ["request", "interview", "checks", "interview", "draft", "package"]
    assert [s["went_back"] for s in steps] == [False, False, False, True, False, False]
    assert steps[1]["details"] == ["Asked: specs?", "Noted specs"]
    assert steps[3]["details"] == ["Asked: why Dell?"]


def test_build_timeline_empty():
    assert build_timeline([]) == []
