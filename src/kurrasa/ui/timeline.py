import html

from kurrasa.services.events import Event

ORDER = ["request", "interview", "checks", "draft", "package", "finance", "legal"]
LABELS = {
    "request": "Request received",
    "interview": "Asking the department",
    "checks": "Checking the company rules",
    "draft": "Writing the tender",
    "package": "Package ready",
    "finance": "Finance review",
    "legal": "Legal review",
}


def build_timeline(events: list[Event]) -> list[dict]:
    """Group consecutive events by stage; mark a step that returns to an earlier stage."""
    steps = []
    for e in events:
        if steps and steps[-1]["stage"] == e.stage:
            steps[-1]["details"].append(e.summary)
            continue
        went_back = bool(steps) and ORDER.index(e.stage) < ORDER.index(steps[-1]["stage"])
        steps.append({"stage": e.stage, "went_back": went_back, "details": [e.summary]})
    return steps


def render_timeline(steps: list[dict], running: bool) -> str:
    """A vertical line from top to bottom, one node per step; returns HTML for st.markdown."""
    rows = []
    for i, step in enumerate(steps):
        current = running and i == len(steps) - 1
        colour = "#e8710a" if step["went_back"] else ("#1a73e8" if current else "#34a853")
        note = "↩ Went back to ask the department" if step["went_back"] else ""
        details = "".join(f"<div style='opacity:.75;font-size:.85em'>{html.escape(d)}</div>" for d in step["details"][-4:])
        more = len(step["details"]) - 4
        if more > 0:
            details = f"<div style='opacity:.5;font-size:.8em'>+{more} earlier</div>" + details
        rows.append(f"""
<div style="display:flex;gap:14px">
  <div style="display:flex;flex-direction:column;align-items:center">
    <div style="width:16px;height:16px;border-radius:50%;background:{colour};{'box-shadow:0 0 0 5px rgba(26,115,232,.25);' if current else ''}"></div>
    <div style="flex:1;width:2px;background:rgba(128,128,128,.35);min-height:24px"></div>
  </div>
  <div style="padding-bottom:16px">
    <div style="font-weight:600">{LABELS.get(step['stage'], step['stage'])}{' · now' if current else ''}</div>
    <div style="color:{colour};font-size:.85em">{note}</div>
    {details}
  </div>
</div>""")
    return "".join(rows)
