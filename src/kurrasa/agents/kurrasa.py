import base64
import mimetypes
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from kurrasa.agents.session import Message, Session
from kurrasa.agents.tools import STAGE_TOOLS, build_tools
from kurrasa.config import MAX_STEPS
from kurrasa.config.prompts import build_agent_prompt
from kurrasa.services.company import fill_template
from kurrasa.services.events import EventLog


def content_blocks(text: str, attachments: list[Path]) -> list[dict]:
    """Text plus files as LangChain standard blocks, so Gemini can read images, PDFs and audio."""
    blocks = [{"type": "text", "text": text}] if text else []
    for path in attachments:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        kind = mime.split("/")[0] if mime.split("/")[0] in ("image", "audio") else "file"
        blocks.append({"type": kind, "base64": base64.b64encode(path.read_bytes()).decode(), "mime_type": mime})
    return blocks


def run_agent(llm, requester, events: EventLog, facts: dict, template: str, publish: date, tender_no: str) -> dict:
    session = Session()
    tools = build_tools(session, requester, events, facts)
    by_name = {t.name: t for t in tools}

    opening: Message = requester.opening()
    session.transcript.append({"role": "requester", "text": opening.text,
                               "attachments": [str(p) for p in opening.attachments]})
    events.emit("request", "opening", f"Request: {opening.text}", {"text": opening.text})
    messages = [SystemMessage(content=build_agent_prompt(facts, publish)),
                HumanMessage(content=content_blocks(opening.text, opening.attachments))]

    stopped_reason = "step_limit"
    for _ in range(MAX_STEPS):
        allowed = STAGE_TOOLS[session.stage]
        ai = llm.bind_tools([by_name[n] for n in allowed]).invoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            messages.append(HumanMessage(content="Use one of your tools to continue."))
            continue

        for call in ai.tool_calls:
            allowed = STAGE_TOOLS[session.stage]   # can change mid-batch after next_stage
            if call["name"] in allowed:
                result = by_name[call["name"]].invoke(call["args"])
            else:
                result = (f"{call['name']} is not available in the {session.stage} stage. "
                          f"Available: {', '.join(allowed)}.")
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

        if session.pending_attachments:
            messages.append(HumanMessage(content=content_blocks("Files the requester attached:",
                                                                session.pending_attachments)))
            session.pending_attachments = []

        if session.finished:
            stopped_reason = "finished"
            break

    tender = fill_template(template, session.sections, publish, tender_no, facts) if session.finished else None
    return {
        "requirements": session.requirements,
        "issues": session.issues,
        "sections": session.sections,
        "route": session.route,
        "questions_asked": session.questions_asked,
        "transcript": session.transcript,
        "tender": tender,
        "tender_no": tender_no,
        "publish": publish.isoformat(),
        "stopped_reason": stopped_reason,
    }
