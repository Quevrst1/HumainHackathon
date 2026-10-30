import argparse
import csv
import json
import re
from math import comb
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage

from kurrasa.config import AGENT_MODELS, JUDGE_MODELS, create_llm
from kurrasa.config.prompts import build_flag_judge_prompt, build_requirements_judge_prompt
from kurrasa.pipeline.plain_chat import run_plain_chat
from kurrasa.pipeline.run import SCENARIOS, run_scenario

ARABIC_DIGITS = str.maketrans("0123456789,", "٠١٢٣٤٥٦٧٨٩٬")


def budget_leaked(tender: str, budget: int) -> bool:
    forms = [str(budget), f"{budget:,}"]
    if budget % 1000 == 0:
        forms.append(f"{budget // 1000} ألف")
    forms += [f.translate(ARABIC_DIGITS) for f in forms]
    # digit lookarounds so 900000 doesn't match inside 1900000
    return any(re.search(rf"(?<![\d٠-٩]){re.escape(f)}(?![\d٠-٩])", tender) for f in forms)


def majority(votes: list[bool]) -> bool:
    return sum(votes) * 2 > len(votes)


def pass_k(successes: list[bool], k: int) -> float:
    """tau-bench pass^k: the chance that k runs of the same scenario all succeed."""
    return comb(sum(successes), k) / comb(len(successes), k)


def ask(judge, prompt: str) -> str:
    return judge.invoke([HumanMessage(content=prompt)]).text.strip()


def flag_list(text: str) -> list[str]:
    start, end = text.find("["), text.rfind("]")
    try:
        return json.loads(text[start:end + 1]) if start != -1 else []
    except json.JSONDecodeError:
        return []


def score_run(run_dir: Path, scenario_dir: Path, judges: list) -> dict:
    package = json.loads((run_dir / "package.json").read_text(encoding="utf-8"))
    tender_path = run_dir / "tender.txt"
    tender = tender_path.read_text(encoding="utf-8") if tender_path.exists() else ""
    scenario = yaml.safe_load((scenario_dir / "scenario.yaml").read_text(encoding="utf-8"))
    key = yaml.safe_load((scenario_dir / "answer_key.yaml").read_text(encoding="utf-8"))
    flags = yaml.safe_load((scenario_dir.parent / "flags.yaml").read_text(encoding="utf-8"))
    hidden = {r["id"]: r["text"] for r in scenario["hidden_requirements"]}
    route = package["route"] or {}
    agreements = []

    found = 0
    if tender:
        wanted = {r: hidden[r] for r in key["must_include"]}
        answers = [flag_list(ask(j, build_requirements_judge_prompt(tender, wanted))) for j in judges]
        for req in wanted:
            votes = [req in a for a in answers]
            agreements.append(len(set(votes)) == 1)
            found += majority(votes)

    detected = []
    issues = [i["description"] for i in package["issues"]]
    if issues:
        answers = [flag_list(ask(j, build_flag_judge_prompt(issues, flags))) for j in judges]
        for flag in flags:
            votes = [flag in a for a in answers]
            agreements.append(len(set(votes)) == 1)
            if majority(votes):
                detected.append(flag)

    expected = set(key["expected_flags"])
    scores = {
        "blanks_filled": bool(tender),
        "method_ok": route.get("method") == key["expected_method"],
        "approver_ok": route.get("approver") == key["expected_approver"],
        "budget_leaked": budget_leaked(tender, key["budget_sar"]),
        "questions_asked": package["questions_asked"],
        "requirements_found": found,
        "requirements_total": len(key["must_include"]),
        "flags_detected": detected,
        "problem_caught": expected <= set(detected) if expected else None,
        "false_alarm": bool(set(detected) - expected),
        "judge_agreement": sum(agreements) / len(agreements) if agreements else None,
    }
    scores["success"] = (scores["blanks_filled"] and scores["method_ok"] and scores["approver_ok"]
                         and not scores["budget_leaked"] and found == scores["requirements_total"]
                         and (scores["problem_caught"] if expected else not scores["false_alarm"]))
    (run_dir / "scores.json").write_text(json.dumps(scores, indent=2), encoding="utf-8")
    return scores


METRICS = ["success", "requirements_found", "requirements_total", "problem_caught", "false_alarm", "method_ok",
           "approver_ok", "budget_leaked", "blanks_filled", "questions_asked", "judge_agreement"]


def summarise(rows: list[dict], k: int = 3) -> list[dict]:
    """tau-bench style summary per condition, separately for the main set and the hold-out pair."""
    out = []
    for group in ("main", "holdout"):
        for condition in ("plain_chat", "agent"):
            subset = [r for r in rows if r["group"] == group and r["condition"] == condition and "error" not in r]
            if not subset:
                continue
            mean = lambda key: sum(r[key] for r in subset if r[key] is not None) / max(1, sum(r[key] is not None for r in subset))
            by_scenario = {}
            for r in subset:
                by_scenario.setdefault(r["scenario"], []).append(r["success"])
            full = [s for s in by_scenario.values() if len(s) >= k]
            out.append({
                "group": group, "condition": condition, "runs": len(subset),
                "successes": f"{sum(r['success'] for r in subset)}/{len(subset)}",
                "pass^1": mean("success"),
                f"pass^{k}": sum(pass_k(s, k) for s in full) / len(full) if full else None,
                "requirements_recall": sum(r["requirements_found"] for r in subset) / sum(r["requirements_total"] for r in subset),
                "problems_caught": mean("problem_caught"), "false_alarms": mean("false_alarm"),
                "route_correct": mean("method_ok") * 0.5 + mean("approver_ok") * 0.5,
                "budget_leaks": mean("budget_leaked"), "avg_questions": mean("questions_asked"),
                "judge_agreement": mean("judge_agreement"),
            })
    return out


def main():
    parser = argparse.ArgumentParser(description="Run every scenario with plain chat (A) and Kurrasa (C), then score them.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenarios", nargs="*", help="default: all scenarios")
    args = parser.parse_args()

    names = args.scenarios or sorted(p.name for p in SCENARIOS.iterdir() if p.is_dir())
    agent_llm = create_llm(**AGENT_MODELS["agent"])
    requester_llm = create_llm(**AGENT_MODELS["requester"])
    judges = [create_llm(**cfg) for cfg in JUDGE_MODELS]

    rows = []
    for name in names:
        group = "holdout" if yaml.safe_load((SCENARIOS / name / "scenario.yaml").read_text(encoding="utf-8"))["holdout"] else "main"
        for i in range(1, args.runs + 1):
            for condition in ("agent", "plain_chat"):
                row = {"scenario": name, "group": group, "condition": condition, "run": i}
                try:
                    run_dir = (run_scenario(name, f"eval{i}", agent_llm, requester_llm, verbose=False)
                               if condition == "agent" else run_plain_chat(name, f"eval{i}", agent_llm, requester_llm))
                    row.update(score_run(run_dir, SCENARIOS / name, judges))
                except Exception as e:   # one failed run (e.g. quota) shouldn't lose the rest
                    row["error"] = str(e)[:200]
                rows.append(row)
                print(f"{name:24} {condition:8} run {i}: {'ERROR ' + row['error'] if 'error' in row else 'scored'}")

    Path("results").mkdir(exist_ok=True)
    with open("results/summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario", "group", "condition", "run", *METRICS, "flags_detected", "error"])
        writer.writeheader()
        writer.writerows({k: v for k, v in r.items() if k in writer.fieldnames} for r in rows)

    for line in summarise(rows, k=args.runs):
        print(" | ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in line.items()))
