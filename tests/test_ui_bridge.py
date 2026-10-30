import time

from fakes import ScriptedLLM, finishing_script
from kurrasa.ui.bridge import AgentRunner, form_message


def wait_for(condition, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_form_message():
    text = form_message("Sales", "We need a modern CRM", 900_000)
    assert text == "Department: Sales\nRequest: We need a modern CRM\nBudget: SAR 900,000"


def test_runner_asks_then_finishes(tmp_path):
    runner = AgentRunner(ScriptedLLM(finishing_script()), out_root=tmp_path)
    runner.start("Sales", "We need a CRM", 900_000)

    assert wait_for(lambda: runner.pending_question() is not None)
    assert runner.pending_question() == "How many users?"
    runner.answer("About 120")

    assert wait_for(lambda: runner.done)
    assert runner.package["stopped_reason"] == "finished"
    assert runner.package["route"]["approver"] == "General Manager"
    assert [m["role"] for m in runner.chat()] == ["requester", "agent", "requester"]
    assert any(e.tool == "finish" for e in runner.events.events)
    assert (runner.out_dir / "package.json").exists() and (runner.out_dir / "tender.txt").exists()


def test_runner_adds_simulated_finance_and_legal_reviews(tmp_path):
    runner = AgentRunner(ScriptedLLM(finishing_script()), out_root=tmp_path)
    runner.start("Sales", "We need a CRM", 900_000)
    assert wait_for(lambda: runner.pending_question() is not None)
    runner.answer("About 120")
    assert wait_for(lambda: runner.done)
    stages = [e.stage for e in runner.events.events]
    assert stages[-2:] == ["finance", "legal"]
    assert [r["step"] for r in runner.package["reviews"]] == ["finance", "legal"]
    assert all(r["simulated"] for r in runner.package["reviews"])
