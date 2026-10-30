import json

from langchain_core.messages import AIMessage

from kurrasa.pipeline.baseline import run_baseline
from kurrasa.services.company import AGENT_BLANKS


class OneShotLLM:
    def __init__(self, text):
        self.text = text

    def invoke(self, messages):
        return AIMessage(content=self.text)


def test_baseline_parses_json_and_fills(tmp_path):
    reply = {"sections": {b: f"نص {b}" for b in AGENT_BLANKS}, "issues": ["vague request"], "budget_sar": 900000}
    out = run_baseline("crm_vague", "b1", OneShotLLM("```json\n" + json.dumps(reply) + "\n```"), out_root=tmp_path)
    assert out == tmp_path / "crm_vague" / "baseline" / "b1"
    package = json.loads((out / "package.json").read_text(encoding="utf-8"))
    assert package["stopped_reason"] == "finished" and package["questions_asked"] == 0
    assert package["route"] == {"method": "limited competition", "approver": "General Manager"}
    assert package["issues"][0]["description"] == "vague request"
    assert "{{" not in (out / "tender.txt").read_text(encoding="utf-8")


def test_baseline_bad_json_is_recorded(tmp_path):
    out = run_baseline("crm_vague", "b2", OneShotLLM("Sorry, I cannot."), out_root=tmp_path)
    package = json.loads((out / "package.json").read_text(encoding="utf-8"))
    assert package["stopped_reason"] == "bad_output" and not (out / "tender.txt").exists()
