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


def test_runner_follows_the_pipeline_order(tmp_path):
    runner = AgentRunner(ScriptedLLM(finishing_script()), out_root=tmp_path)
    runner.start("Sales", "We need a CRM", 900_000)
    assert wait_for(lambda: runner.pending_question() is not None)
    runner.answer("About 120")
    assert wait_for(lambda: runner.done)
    stages = [e.stage for e in runner.events.events]
    assert stages[:2] == ["request", "finance"]          # Finance checks the budget before procurement starts
    assert stages[-2:] == ["legal", "generation"]        # Legal reviews the draft, then the tender + PDF are generated
    assert [r["step"] for r in runner.package["reviews"]] == ["finance", "legal"]
    assert all(r["simulated"] for r in runner.package["reviews"])


def test_finance_cannot_confirm_its_own_budget():
    from kurrasa.services.events import EventLog
    from kurrasa.ui.bridge import finance_review
    finance = finance_review(EventLog(), "Finance", 400_000)
    assert finance["status"] == "escalated" and "General Manager" in finance["note"]
    assert finance_review(EventLog(), "Sales", 400_000)["status"] == "approved"


def test_budget_change_goes_back_to_finance(tmp_path):
    # the form says 50,000 but the agent settles on 900,000 (finishing_script calls purchase_route(900000))
    runner = AgentRunner(ScriptedLLM(finishing_script()), out_root=tmp_path)
    runner.start("Sales", "We need a CRM", 50_000)
    assert wait_for(lambda: runner.pending_question() is not None)
    runner.answer("Actually our budget is 900,000")
    assert wait_for(lambda: runner.done)
    finance = [e for e in runner.events.events if e.stage == "finance"]
    assert len(finance) == 2
    assert "50,000" in finance[1].summary and "900,000" in finance[1].summary
    assert [r["step"] for r in runner.package["reviews"]] == ["finance", "finance", "legal"]


def test_same_budget_is_not_rechecked(tmp_path):
    runner = AgentRunner(ScriptedLLM(finishing_script()), out_root=tmp_path)
    runner.start("Sales", "We need a CRM", 900_000)
    assert wait_for(lambda: runner.pending_question() is not None)
    runner.answer("120")
    assert wait_for(lambda: runner.done)
    assert sum(e.stage == "finance" for e in runner.events.events) == 1
