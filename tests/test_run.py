import json

from langchain_core.messages import AIMessage

from fakes import ScriptedLLM, finishing_script
from kurrasa.pipeline.run import run_scenario


class EchoLLM:
    def invoke(self, messages):
        return AIMessage(content="About 120 users.")


def test_run_scenario_writes_outputs(tmp_path):
    out = run_scenario("crm_clean", "t1", ScriptedLLM(finishing_script()), EchoLLM(), out_root=tmp_path, verbose=False)
    assert out == tmp_path / "crm_clean" / "agent" / "t1"
    for name in ["transcript.json", "events.jsonl", "tender.txt", "package.json"]:
        assert (out / name).exists(), name
    package = json.loads((out / "package.json").read_text(encoding="utf-8"))
    assert package["stopped_reason"] == "finished" and "tender" not in package


def test_run_scenario_sends_steps_to_a_custom_listener(tmp_path):
    seen = []
    run_scenario("crm_clean", "t2", ScriptedLLM(finishing_script()), EchoLLM(), out_root=tmp_path, verbose=False,
                 listener=seen.append)
    assert [e.tool for e in seen][:2] == ["opening", "ask_requester"] and seen[-1].tool == "finish"
