"""Check every scenario against the flag list and the company's procurement rules."""

from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "scenarios"


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def tier(value: int, tiers: list[dict], field: str) -> str:
    # first tier whose ceiling covers the value; a null ceiling means no limit
    return next(t[field] for t in tiers if t["max_sar"] is None or value <= t["max_sar"])


def check(name: str, sc: dict, key: dict, flags: dict, policy: dict) -> list[str]:
    problems = []
    hidden = {r["id"]: r["text"] for r in sc["hidden_requirements"]}

    if sc["id"] != name:
        problems.append(f"id '{sc['id']}' does not match the folder name")
    problems += [f"unknown flag '{f}'" for f in key["expected_flags"] if f not in flags]
    problems += [f"must_include '{r}' is not a hidden requirement" for r in key["must_include"] if r not in hidden]

    # the budget is confidential: the requester holds it, the tender must never contain it
    budget = key["budget_sar"]
    if f"{budget:,}" not in hidden.get("budget", ""):
        problems.append(f"requester has no hidden budget of {budget:,}")
    if "budget" in key["must_include"]:
        problems.append("budget must not be in must_include")

    method = tier(budget, policy["methods"], "method")
    approver = tier(budget, policy["approval_matrix"], "approver")
    if key["expected_method"] != method:
        problems.append(f"expected_method should be '{method}'")
    if key["expected_approver"] != approver:
        problems.append(f"expected_approver should be '{approver}'")

    return [f"{name}: {p}" for p in problems]


def check_pairs(scenarios: list[dict]) -> list[str]:
    problems = []
    pairs = defaultdict(list)
    for s in scenarios:
        pairs[s["pair"]].append(s)

    for pair, members in pairs.items():
        if sorted(m["variant"] for m in members) != ["clean", "problem"]:
            problems.append(f"pair {pair}: needs exactly one clean and one problem variant")
            continue
        for m in members:
            if (m["variant"] == "problem") != bool(m["expected_flags"]):
                problems.append(f"{m['id']}: problem variants need flags, clean ones must have none")
        if len({m["holdout"] for m in members}) > 1:
            problems.append(f"pair {pair}: both variants must share holdout status")
    return problems


def main():
    flags = load(SCENARIOS / "flags.yaml")
    policy = load(ROOT / "data" / "company" / "facts.yaml")["procurement_policy"]
    scenarios, problems = [], []

    for folder in sorted(p for p in SCENARIOS.iterdir() if p.is_dir()):
        sc, key = load(folder / "scenario.yaml"), load(folder / "answer_key.yaml")
        problems += check(folder.name, sc, key, flags, policy)
        scenarios.append({**sc, **key})
    problems += check_pairs(scenarios)

    for p in problems:
        print(p)
    if problems:
        raise SystemExit(1)
    print(f"{len(scenarios)} scenarios valid")


if __name__ == "__main__":
    main()
