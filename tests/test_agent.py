from datetime import date

from langchain_core.messages import AIMessage, HumanMessage

from kurrasa.agents.kurrasa import run_agent
from kurrasa.agents.session import Message
from kurrasa.config.prompts import build_agent_prompt
from kurrasa.services.company import AGENT_BLANKS, load_facts, load_template
from kurrasa.services.events import EventLog


class ScriptedLLM:
    def __init__(self, replies, repeat_last=False):
        self.replies = list(replies)
        self.repeat_last = repeat_last
        self.received = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.received.append(list(messages))
        if self.repeat_last and len(self.replies) == 1:
            return self.replies[0]
        return self.replies.pop(0)


class StubRequester:
    def __init__(self, replies=()):
        self.replies = list(replies)

    def opening(self):
        return Message(text="We need a CRM.")

    def reply(self, question):
        return self.replies.pop(0) if self.replies else Message(text="ok")


def call(name, args, i=0):
    return {"name": name, "args": args, "id": f"{name}-{i}"}


def finishing_script():
    writes = [call("write_section", {"name": b, "text": f"نص {b}"}, i) for i, b in enumerate(AGENT_BLANKS)]
    return [
        AIMessage(content="", tool_calls=[call("ask_requester", {"question": "How many users?"})]),
        AIMessage(content="", tool_calls=[call("purchase_route", {"budget_sar": 900_000})]),
        AIMessage(content="", tool_calls=writes),
        AIMessage(content="", tool_calls=[call("finish", {})]),
    ]


def run(llm, requester=None):
    return run_agent(llm, requester or StubRequester(), EventLog(), load_facts(), load_template(),
                     date(2026, 11, 1), "SAHAB-T")


def test_full_scripted_run_produces_tender():
    package = run(ScriptedLLM(finishing_script()))
    assert package["stopped_reason"] == "finished"
    assert "{{" not in package["tender"]
    assert package["route"] == {"method": "limited competition", "approver": "General Manager"}
    assert package["questions_asked"] == 1


def test_plain_text_reply_gets_nudged():
    llm = ScriptedLLM([AIMessage(content="Let me think."), *finishing_script()])
    run(llm)
    assert llm.received[1][-1].content == "Use one of your tools to continue."


def test_step_limit_stops_loop():
    ask = AIMessage(content="", tool_calls=[call("record_requirement", {"name": "x", "value": "y"})])
    package = run(ScriptedLLM([ask], repeat_last=True))
    assert package["stopped_reason"] == "step_limit" and package["tender"] is None


def test_attachment_becomes_content_block(tmp_path):
    image = tmp_path / "photo.png"
    image.write_bytes(b"\x89PNG fake")
    llm = ScriptedLLM(finishing_script())
    run(llm, StubRequester([Message(text="see photo", attachments=[image])]))
    after_ask = llm.received[1][-1]
    assert isinstance(after_ask, HumanMessage)
    assert any(isinstance(b, dict) and b.get("type") == "image" for b in after_ask.content)


def test_agent_prompt_is_generic():
    p = build_agent_prompt({"company": {}})
    for word in ["brand_lock", "data_residency", "Dell", "Frankfurt", "modern"]:
        assert word not in p
    assert "purchase_route" in p and "finish" in p
