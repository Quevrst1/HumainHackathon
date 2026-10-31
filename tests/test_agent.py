from datetime import date

from langchain_core.messages import AIMessage, HumanMessage

from kurrasa.agents.kurrasa import run_agent
from kurrasa.agents.session import Message
from kurrasa.agents.tools import STAGE_TOOLS
from fakes import ScriptedLLM, StubRequester, call, finishing_script
from kurrasa.config.prompts import build_agent_prompt
from kurrasa.services.company import load_facts, load_template
from kurrasa.services.events import EventLog


def run(llm, requester=None):
    return run_agent(llm, requester or StubRequester(), EventLog(), load_facts(), load_template(),
                     date(2026, 11, 1), "SAHAB-T")


def test_full_scripted_run_produces_tender():
    package = run(ScriptedLLM(finishing_script()))
    assert package["stopped_reason"] == "finished"
    assert "{{" not in package["tender"]
    assert package["route"] == {"method": "limited competition", "approver": "General Manager"}
    assert package["questions_asked"] == 1
    assert package["tender_no"] == "SAHAB-T" and package["publish"] == "2026-11-01"


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
    p = build_agent_prompt({"company": {}}, date(2026, 11, 1))
    for word in ["brand_lock", "data_residency", "Dell", "Frankfurt", "modern"]:
        assert word not in p
    assert "purchase_route" in p and "finish" in p


def test_agent_prompt_has_date_and_record_rule():
    p = build_agent_prompt({"company": {}}, date(2026, 11, 1))
    assert "2026-11-01" in p and "even if you fix it" in p


def test_agent_prompt_asks_for_specifics_and_measurable_acceptance():
    p = build_agent_prompt({"company": {}}, date(2026, 11, 1))
    assert "the usual" in p and "measurable" in p
    for word in ["cleaning", "service level", "SLA", "inspection"]:   # still generic: no planted-problem names
        assert word.lower() not in p.lower()


def test_each_step_binds_only_the_current_stage_tools():
    llm = ScriptedLLM(finishing_script())
    run(llm)
    assert llm.bound[0] == set(STAGE_TOOLS["interview"])
    assert set(STAGE_TOOLS["draft"]) in llm.bound


def test_out_of_stage_tool_is_refused():
    early_write = AIMessage(content="", tool_calls=[call("write_section", {"name": "TITLE", "text": "t"})])
    llm = ScriptedLLM([early_write, *finishing_script()])
    package = run(llm)
    assert "not available in the interview stage" in llm.received[1][-1].content
    assert package["stopped_reason"] == "finished"
