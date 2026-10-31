import argparse
import csv
import json
import re
from datetime import datetime
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
        items = json.loads(text[start:end + 1]) if start != -1 else []
    except json.JSONDecodeError:
        return []
    # some judges add an explanation after the id ("users: 120 users"); keep just the id
    return [str(i).split(":")[0].strip() for i in items]


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


def group_of(name: str) -> str:
    return "holdout" if yaml.safe_load((SCENARIOS / name / "scenario.yaml").read_text(encoding="utf-8"))["holdout"] else "main"


def log(text: str):
    indent = "    " if text.startswith("    ") else ""
    print(f"{datetime.now():%H:%M:%S}  {indent}{' '.join(text.split())}", flush=True)


def log_step(event):
    """The agent steps worth seeing in the experiment log."""
    if event.tool == "ask_requester" and "question" in event.data:
        log(f"    asked: {' '.join(event.data['question'].split())[:110]}")
    elif event.tool == "purchase_route":
        log(f"    route: {event.summary}")
    elif event.tool == "raise_issue":
        log(f"    issue: {event.data.get('description', '')[:100]}")
    elif event.tool == "resolve_issue" and event.data.get("resolution"):
        log(f"    resolved: {event.data['resolution'][:100]}")


def result_line(s: dict) -> str:
    check = "problem caught" if s["problem_caught"] is not None else "false alarm"
    value = s["problem_caught"] if s["problem_caught"] is not None else s["false_alarm"]
    agreement = f"{s['judge_agreement']:.0%}" if s["judge_agreement"] is not None else "n/a"
    return (f"{'success' if s['success'] else 'fail'} | requirements {s['requirements_found']}/{s['requirements_total']}"
            f" | {check}: {'yes' if value else 'no'} | route {'ok' if s['method_ok'] and s['approver_ok'] else 'wrong'}"
            f" | budget leaked: {'yes' if s['budget_leaked'] else 'no'} | {s['questions_asked']} questions"
            f" | judges agree {agreement}")


def scored_row(name: str, condition: str, i: int, run_and_score, label: str = "") -> dict:
    row = {"scenario": name, "group": group_of(name), "condition": condition, "run": i}
    log(f"{label}{name} / {'kurrasa' if condition == 'agent' else condition} / run {i}")
    try:
        row.update(run_and_score())
        log(f"    -> {result_line(row)}")
    except Exception as e:   # one failed run or judge call (e.g. quota) shouldn't lose the rest
        row["error"] = str(e)[:200]
        log(f"    -> error: {row['error']}")
    return row


def rescore(results_root: Path, names: list[str], runs: int, judges: list) -> list[dict]:
    """Score runs already saved under results_root again, without re-running the agent (e.g. after a judge quota ran out)."""
    rows = []
    for name in names:
        for i in range(1, runs + 1):
            for condition in ("agent", "plain_chat"):
                run_dir = results_root / name / condition / f"eval{i}"
                if (run_dir / "package.json").exists():
                    rows.append(scored_row(name, condition, i, lambda: score_run(run_dir, SCENARIOS / name, judges)))
    return rows


def write_summary(rows: list[dict], k: int, out: Path = Path("results")):
    out.mkdir(exist_ok=True)
    with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario", "group", "condition", "run", *METRICS, "flags_detected", "error"])
        writer.writeheader()
        writer.writerows({key: v for key, v in r.items() if key in writer.fieldnames} for r in rows)
    for line in summarise(rows, k=k):
        print(" | ".join(f"{key}={v:.2f}" if isinstance(v, float) else f"{key}={v}" for key, v in line.items()))


def main():
    parser = argparse.ArgumentParser(description="Run every scenario with plain chat (A) and Kurrasa (C), then score them.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenarios", nargs="*", help="default: all scenarios")
    parser.add_argument("--rescore", action="store_true", help="only re-score runs already saved in results/")
    args = parser.parse_args()

    names = args.scenarios or sorted(p.name for p in SCENARIOS.iterdir() if p.is_dir())
    judges = [create_llm(**cfg) for cfg in JUDGE_MODELS]

    if args.rescore:
        rows = rescore(Path("results"), names, args.runs, judges)
    else:
        agent_llm = create_llm(**AGENT_MODELS["agent"])
        requester_llm = create_llm(**AGENT_MODELS["requester"])
        rows, total = [], len(names) * args.runs * 2
        log(f"experiment: {len(names)} scenarios x {args.runs} runs x 2 conditions = {total} runs")
        log(f"agent and requester: {AGENT_MODELS['agent']['model']} | judges: {', '.join(j['model'] for j in JUDGE_MODELS)}")
        for name in names:
            for i in range(1, args.runs + 1):
                rows.append(scored_row(name, "agent", i, lambda: score_run(
                    run_scenario(name, f"eval{i}", agent_llm, requester_llm, verbose=False, listener=log_step),
                    SCENARIOS / name, judges), label=f"[{len(rows) + 1}/{total}] "))
                rows.append(scored_row(name, "plain_chat", i, lambda: score_run(
                    run_plain_chat(name, f"eval{i}", agent_llm, requester_llm), SCENARIOS / name, judges),
                    label=f"[{len(rows) + 1}/{total}] "))
        log("all runs finished")

    write_summary(rows, k=args.runs)
