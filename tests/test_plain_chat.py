import json

from langchain_core.messages import AIMessage

from kurrasa.pipeline.plain_chat import run_plain_chat
from kurrasa.services.company import AGENT_BLANKS

FINAL = json.dumps({"sections": {b: f"نص {b}" for b in AGENT_BLANKS}, "issues": ["x"], "budget_sar": 900000})


class Turns:
    def __init__(self, turns, repeat_last=False):
        self.turns, self.repeat_last, self.received = list(turns), repeat_last, []

    def invoke(self, messages):
        self.received.append(list(messages))
        text = self.turns[0] if self.repeat_last and len(self.turns) == 1 else self.turns.pop(0)
        return AIMessage(content=text)


def package(out):
    return json.loads((out / "package.json").read_text(encoding="utf-8"))


def test_plain_chat_asks_then_finishes(tmp_path):
    out = run_plain_chat("crm_vague", "p1", Turns(["How many users?", "Which systems?", FINAL]),
                         Turns(["120"], repeat_last=True), out_root=tmp_path)
    p = package(out)
    assert out == tmp_path / "crm_vague" / "plain_chat" / "p1"
    assert p["questions_asked"] == 2 and p["stopped_reason"] == "finished"
    assert p["route"] == {"method": "limited competition", "approver": "General Manager"}
    assert (out / "tender.txt").exists() and (out / "transcript.json").exists()


def test_plain_chat_question_cap(tmp_path):
    llm = Turns(["Another question?"], repeat_last=True)
    p = package(run_plain_chat("crm_vague", "p2", llm, Turns(["ok"], repeat_last=True), out_root=tmp_path))
    assert p["questions_asked"] == 10 and p["stopped_reason"] == "bad_output"
    assert "Question limit reached" in llm.received[-1][-1].content


def test_plain_chat_bad_output(tmp_path):
    llm = Turns(['{"sections": {"TITLE": "x"}}'])
    p = package(run_plain_chat("crm_vague", "p3", llm, Turns(["ok"], repeat_last=True), out_root=tmp_path))
    assert p["stopped_reason"] == "bad_output" and not (tmp_path / "crm_vague" / "plain_chat" / "p3" / "tender.txt").exists()
