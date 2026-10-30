import json
from pathlib import Path

from langchain_core.messages import AIMessage

from kurrasa.pipeline.evaluate import budget_leaked, majority, score_run


class ScriptedJudge:
    """Says YES to every requirement and reports the given flags for any issue list."""

    def __init__(self, flags):
        self.flags = flags

    def invoke(self, messages):
        prompt = messages[-1].content
        return AIMessage(content="YES" if "Answer YES or NO" in prompt else json.dumps(self.flags))


def make_run(tmp_path, route, issues, tender="نطاق العمل لـ 200 جهاز"):
    (tmp_path / "package.json").write_text(json.dumps({
        "requirements": {}, "issues": [{"id": 1, "description": d, "status": "open", "resolution": None} for d in issues],
        "sections": {}, "route": route, "questions_asked": 4, "stopped_reason": "finished"}), encoding="utf-8")
    (tmp_path / "tender.txt").write_text(tender, encoding="utf-8")
    return tmp_path


GM_GENERAL = {"method": "general competition", "approver": "General Manager"}


def test_budget_leak_formats():
    for t in ["الميزانية 900000", "900,000 ريال", "٩٠٠٬٠٠٠", "900 ألف ريال"]:
        assert budget_leaked(t, 900_000), t
    assert not budget_leaked("نطاق العمل لـ 120 مستخدماً", 900_000)
    assert not budget_leaked("1900000", 900_000)


def test_majority():
    assert majority([True, True, False]) and not majority([True, False, False]) and majority([True])


def test_score_run_code_checks(tmp_path):
    run = make_run(tmp_path, GM_GENERAL, ["Spec names Dell only"])
    s = score_run(run, Path("scenarios/laptops_brand_locked"), [ScriptedJudge(["brand_lock"])])
    assert s["method_ok"] and s["approver_ok"] and not s["budget_leaked"]
    assert s["requirements_found"] == s["requirements_total"] == 6
    assert s["problem_caught"] and not s["false_alarm"]
    assert json.loads((run / "scores.json").read_text())["problem_caught"]


def test_false_alarm_on_clean(tmp_path):
    run = make_run(tmp_path, GM_GENERAL, ["Spec names Dell only"])
    s = score_run(run, Path("scenarios/laptops_clean"), [ScriptedJudge(["brand_lock"])])
    assert s["false_alarm"] and s["problem_caught"] is None


def test_summarise_separates_holdout_and_conditions():
    from kurrasa.pipeline.evaluate import summarise
    base = dict(requirements_total=6, problem_caught=None, false_alarm=False, method_ok=True, approver_ok=True,
                budget_leaked=False, blanks_filled=True, questions_asked=4, judge_agreement=1.0)
    rows = [
        {**base, "group": "main", "condition": "agent", "requirements_found": 6},
        {**base, "group": "main", "condition": "agent", "requirements_found": 3},
        {**base, "group": "main", "condition": "baseline", "requirements_found": 0},
        {**base, "group": "holdout", "condition": "agent", "requirements_found": 6},
        {"group": "main", "condition": "agent", "error": "quota"},
    ]
    out = {(r["group"], r["condition"]): r for r in summarise(rows)}
    assert out[("main", "agent")]["runs"] == 2 and out[("main", "agent")]["requirements_recall"] == 0.75
    assert out[("main", "baseline")]["requirements_recall"] == 0
    assert out[("holdout", "agent")]["runs"] == 1
