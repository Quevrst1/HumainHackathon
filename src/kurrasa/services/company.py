import re
from datetime import date, timedelta
from pathlib import Path

import yaml

COMPANY = Path(__file__).resolve().parents[3] / "data" / "company"

# Template blanks the agent writes; TENDER_NO, PUBLISH_DATE and KEY_DATES are filled by code.
AGENT_BLANKS = [
    "TITLE", "OVERVIEW", "SCOPE", "TIMELINE", "LOCATION", "DELIVERABLES",
    "SPECIFICATIONS", "EVALUATION_CRITERIA", "PAYMENT_SCHEDULE", "SPECIAL_CONDITIONS",
]


def load_facts() -> dict:
    return yaml.safe_load((COMPANY / "facts.yaml").read_text(encoding="utf-8"))


def load_template() -> str:
    text = (COMPANY / "tender_template.txt").read_text(encoding="utf-8")
    return re.sub(r"\A\{\{!.*?\}\}\n", "", text, flags=re.S)


def purchase_route(budget_sar: int, facts: dict) -> dict:
    if budget_sar <= 0:
        raise ValueError("budget must be a positive amount in SAR")

    def first_tier(tiers, field):
        return next(t[field] for t in tiers if t["max_sar"] is None or budget_sar <= t["max_sar"])

    policy = facts["procurement_policy"]
    return {
        "method": first_tier(policy["methods"], "method"),
        "approver": first_tier(policy["approval_matrix"], "approver"),
    }


def key_dates(facts: dict, publish: date) -> str:
    period = facts["procurement_policy"]["clarification_period"]
    questions = publish + timedelta(days=period["questions_deadline_days"])
    answers = questions + timedelta(days=period["answers_deadline_days"])
    return "\n".join([
        f"- تاريخ طرح المنافسة: {publish.isoformat()}",
        f"- آخر موعد لاستقبال الاستفسارات: {questions.isoformat()}",
        f"- آخر موعد للرد على الاستفسارات: {answers.isoformat()}",
    ])


def fill_template(template: str, sections: dict[str, str], publish: date, tender_no: str, facts: dict) -> str:
    values = {
        **sections,
        "TENDER_NO": tender_no,
        "PUBLISH_DATE": publish.isoformat(),
        "KEY_DATES": key_dates(facts, publish),
    }
    missing = [name for name in re.findall(r"\{\{(\w+)\}\}", template) if not values.get(name)]
    if missing:
        raise ValueError(f"unfilled blanks: {', '.join(missing)}")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)
