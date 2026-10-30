import html

from kurrasa.services.events import Event

NODES = ["department", "finance", "procurement", "legal", "generation", "done"]
STAGE_TO_NODE = {"request": "department", "finance": "finance", "interview": "procurement", "checks": "procurement",
                 "draft": "procurement", "package": "procurement", "legal": "legal", "generation": "generation"}
COLOURS = {"done": "#34a853", "active": "#1a73e8", "waiting": "#e8710a", "escalated": "#e8710a", "pending": "#9aa0a6"}
ICONS = {"done": "✓", "active": "●", "waiting": "?", "escalated": "↗", "pending": "○"}


def pipeline_state(events: list[Event], department: str, waiting: bool, finished: bool) -> list[dict]:
    """State of each box in the full pipeline, from the agent's events."""
    reached = [STAGE_TO_NODE[e.stage] for e in events if e.stage in STAGE_TO_NODE]
    current = "done" if finished else (reached[-1] if reached else "department")
    finance = next((e for e in events if e.stage == "finance"), None)
    questions = sum(e.tool == "ask_requester" for e in events)
    last_procurement = next((e.summary for e in reversed(events) if STAGE_TO_NODE.get(e.stage) == "procurement"), "")

    nodes = []
    for node in NODES:
        index, current_index = NODES.index(node), NODES.index(current)
        state = "done" if index < current_index or (finished and node == "done") else \
                "active" if index == current_index else "pending"
        if node == "department" and waiting:
            state = "waiting"
        if node == "finance" and finance and finance.data.get("status") == "escalated":
            state = "escalated"
        detail = {
            "department": "waiting for your answer" if waiting else "raised the request",
            "finance": "sent to the General Manager" if state == "escalated" else "budget check (simulated)",
            "procurement": f"Kurrasa · {questions} questions" + (f" · {last_procurement}" if last_procurement and state == "active" else ""),
            "legal": "terms review (simulated)",
            "generation": "tender + PDF",
            "done": "ready to publish",
        }[node]
        label = department if node == "department" else {"finance": "Finance", "procurement": "Procurement",
                                                         "legal": "Legal", "generation": "Generation", "done": "Done"}[node]
        nodes.append({"node": node, "label": label, "state": state, "detail": detail})
    return nodes


def render_pipeline(nodes: list[dict]) -> str:
    """Boxes left to right with arrows; returns HTML for st.markdown."""
    boxes = []
    for n in nodes:
        colour = COLOURS[n["state"]]
        glow = f"box-shadow:0 0 0 4px {colour}33;" if n["state"] in ("active", "waiting") else ""
        boxes.append(f"""
<div style="border:2px solid {colour};border-radius:10px;padding:10px 12px;min-width:120px;{glow}">
  <div style="font-weight:600"><span style="color:{colour}">{ICONS[n['state']]}</span> {html.escape(n['label'])}</div>
  <div style="font-size:.8em;opacity:.75">{html.escape(n['detail'][:80])}</div>
</div>""")
    arrow = '<div style="align-self:center;opacity:.5;font-size:1.3em">→</div>'
    return f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:stretch">{arrow.join(boxes)}</div>'
