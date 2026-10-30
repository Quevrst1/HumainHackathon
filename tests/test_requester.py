from pathlib import Path

import yaml
from langchain_core.messages import AIMessage

from kurrasa.agents.requester import HumanRequester, SimulatedRequester
from kurrasa.config.prompts import build_requester_prompt


def scenario(name):
    return yaml.safe_load(Path(f"scenarios/{name}/scenario.yaml").read_text(encoding="utf-8"))


class EchoLLM:
    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=f"answer {len(self.calls)}")


def lines(*items):
    it = iter(items)
    return lambda prompt: next(it)


def test_human_file_and_text():
    r = HumanRequester(input_fn=lines("/file data/company/facts.yaml", "here is the spec"))
    m = r.reply("anything?")
    assert m.text == "here is the spec" and m.attachments == [Path("data/company/facts.yaml")]
    assert not m.done


def test_human_done():
    r = HumanRequester(input_fn=lines("/done"))
    assert r.reply("more?").done


def test_requester_prompt_has_persona_not_answers():
    p = build_requester_prompt(scenario("crm_vague"))
    assert "Faisal" in p and "Odoo 16" in p and "only when" in p
    assert "expected_flags" not in p and "vague_request" not in p


def test_simulated_opening_and_history():
    llm = EchoLLM()
    r = SimulatedRequester(scenario("crm_vague"), llm)
    assert r.opening().text == scenario("crm_vague")["opening_request"]
    assert r.reply("How many users?").text == "answer 1"
    r.reply("Which systems?")
    second_call_text = " ".join(str(m.content) for m in llm.calls[1])
    assert "How many users?" in second_call_text and "answer 1" in second_call_text


class ThinkingLLM:
    def invoke(self, messages):
        return AIMessage(content=[{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "About 120 users."}])


def test_simulated_reads_only_text_from_thinking_models():
    r = SimulatedRequester(scenario("crm_vague"), ThinkingLLM())
    assert r.reply("How many users?").text == "About 120 users."
