import json
import re
from pathlib import Path

from langchain_core.messages import AIMessage

from kurrasa.pipeline.evaluate import budget_leaked, majority, pass_k, score_run


class ScriptedJudge:
    """Reports the given requirement ids as present and the given flags for any issue list; counts calls."""

    def __init__(self, flags, found=None):
        self.flags, self.found, self.calls = flags, found, 0

    def invoke(self, messages):
        self.calls += 1
        prompt = messages[-1].content
        if "requirement IDs" in prompt:
            ids = self.found if self.found is not None else re.findall(r"^- (\w+):", prompt, flags=re.M)
            return AIMessage(content=json.dumps(ids))
        return AIMessage(content=json.dumps(self.flags))


def make_run(tmp_path, route, issues, tender="نطاق العمل لـ 200 جهاز"):
    tmp_path.mkdir(parents=True, exist_ok=True)
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
    base = dict(scenario="s1", success=True, requirements_total=6, problem_caught=None, false_alarm=False, method_ok=True, approver_ok=True,
                budget_leaked=False, blanks_filled=True, questions_asked=4, judge_agreement=1.0)
    rows = [
        {**base, "group": "main", "condition": "agent", "requirements_found": 6},
        {**base, "group": "main", "condition": "agent", "requirements_found": 3},
        {**base, "group": "main", "condition": "plain_chat", "requirements_found": 0},
        {**base, "group": "holdout", "condition": "agent", "requirements_found": 6},
        {"group": "main", "condition": "agent", "error": "quota"},
    ]
    out = {(r["group"], r["condition"]): r for r in summarise(rows)}
    assert out[("main", "agent")]["runs"] == 2 and out[("main", "agent")]["requirements_recall"] == 0.75
    assert out[("main", "plain_chat")]["requirements_recall"] == 0
    assert out[("holdout", "agent")]["runs"] == 1


def test_pass_k():
    assert pass_k([True, True, False], 1) == 2 / 3
    assert pass_k([True, True, False], 3) == 0
    assert pass_k([True, True, True], 3) == 1


def test_success_requires_everything(tmp_path):
    full = score_run(make_run(tmp_path / "a", GM_GENERAL, ["Dell named"]), Path("scenarios/laptops_brand_locked"),
                     [ScriptedJudge(["brand_lock"])])
    missing_one = score_run(make_run(tmp_path / "b", GM_GENERAL, ["Dell named"]), Path("scenarios/laptops_brand_locked"),
                            [ScriptedJudge(["brand_lock"], found=["split", "std_spec", "eng_spec", "os_entra", "keyboard"])])
    assert full["success"] and not missing_one["success"]


def test_batched_requirement_judge(tmp_path):
    judge = ScriptedJudge(["brand_lock"])
    score_run(make_run(tmp_path, GM_GENERAL, ["Dell named"]), Path("scenarios/laptops_brand_locked"), [judge])
    assert judge.calls == 2   # one call for all requirements, one for the issues


def test_rescore_scores_saved_runs_without_rerunning(tmp_path):
    from kurrasa.pipeline.evaluate import rescore
    make_run(tmp_path / "laptops_brand_locked" / "agent" / "eval1", GM_GENERAL, ["Dell named"])
    make_run(tmp_path / "laptops_brand_locked" / "plain_chat" / "eval1", GM_GENERAL, [])
    rows = rescore(tmp_path, ["laptops_brand_locked", "laptops_clean"], runs=2, judges=[ScriptedJudge(["brand_lock"])])
    assert [(r["condition"], r["run"]) for r in rows] == [("agent", 1), ("plain_chat", 1)]   # missing runs skipped
    assert rows[0]["problem_caught"] and rows[0]["group"] == "main"
    assert (tmp_path / "laptops_brand_locked" / "agent" / "eval1" / "scores.json").exists()


def test_flag_list_tolerates_ids_with_explanations():
    from kurrasa.pipeline.evaluate import flag_list
    assert flag_list('["users: 120 users", "odoo"]') == ["users", "odoo"]
    assert flag_list('Answer: ["brand_lock"]') == ["brand_lock"]
    assert flag_list("none apply") == []
