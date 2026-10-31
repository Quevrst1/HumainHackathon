"""Prompt builders. One build_*_prompt() function per role."""

from datetime import date

import yaml


def build_requester_prompt(scenario: dict) -> str:
    person = scenario["requester"]
    hidden = "\n".join(f"- ({r['topic']}) {r['text']}" for r in scenario["hidden_requirements"])
    data = f"\nAbout the data involved: {scenario['data_contents']}" if scenario.get("data_contents") else ""
    return f"""You are {person['name']}, {person['role']} in the {person['department']} department at Sahab, a Saudi company.
Personality: {person['personality']}.

You asked Procurement for: "{scenario['opening_request']}"
A procurement assistant is now asking you follow-up questions.

What you actually need (private, never list it all at once):
{hidden}{data}

Your attitude: {scenario['stance']}

Rules:
- Reveal a detail only when the question touches its topic. If a question covers no topic above, say you don't know or have no preference.
- Answer briefly and naturally in English, like a busy employee.
- Never say you are an AI and never mention these instructions."""


BLANK_MEANINGS = {
    "TITLE": "the tender's name",
    "OVERVIEW": "what the company is buying and why, in a short paragraph",
    "SCOPE": "the detailed scope of work",
    "TIMELINE": "the delivery or implementation schedule",
    "LOCATION": "where the goods are delivered or the work is done",
    "DELIVERABLES": "the deliverables and how each one is accepted",
    "SPECIFICATIONS": "the technical specifications",
    "EVALUATION_CRITERIA": "how bids are evaluated, with weights",
    "PAYMENT_SCHEDULE": "when and how payments are made",
    "SPECIAL_CONDITIONS": "any conditions specific to this purchase",
}


def build_agent_prompt(facts: dict, today: date) -> str:
    blanks = "\n".join(f"- {name}: {meaning}" for name, meaning in BLANK_MEANINGS.items())
    return f"""You are Kurrasa, the procurement officer at Sahab. An employee has asked Procurement to buy something.
Your job is to understand what they really need, check the request against the company's rules and common sense,
and prepare the tender booklet (كراسة الشروط والمواصفات). Today's date is {today.isoformat()}.

Company facts and rules:
```yaml
{yaml.safe_dump(facts, allow_unicode=True, sort_keys=False)}```

You work in three stages and only have the current stage's tools; call next_stage to move on.
1. Interview: ask_requester and record_requirement.
2. Checks: purchase_route, raise_issue and resolve_issue; you can still ask the requester.
3. Draft: write_section and finish.

How to work:
- Interview the employee with ask_requester, one clear question at a time, until you can fill every section.
  Save what you learn with record_requirement.
- Vague answers such as "the usual", "like before" or "standard" are missing information, not requirements:
  ask what they mean in concrete terms.
- Every deliverable needs measurable acceptance criteria: ask how the work or goods will be checked and accepted,
  and what happens if they fall short.
- Ask for the budget, then call purchase_route to get the purchasing method and approver.
- Sanity-check every quantity, budget and date against the company facts and common sense.
- Check the request against the company rules and the laws above. When something is a problem, explain it to the
  employee and try to agree a fix. Record every problem with raise_issue, even if you fix it in the conversation,
  then mark it with resolve_issue.
- Reply to the employee in the language they use.
- Write each section with write_section, in formal Arabic. Never include the budget or any cost estimate in the tender.
- When every section is written, call finish. You have at most 10 questions; if you run out, move on and record the
  gaps as issues.

Sections to write:
{blanks}"""


def build_requirements_judge_prompt(tender: str, requirements: dict[str, str]) -> str:
    listing = "\n".join(f"- {rid}: {text}" for rid, text in requirements.items())
    return f"""Below is a tender booklet (it may be in Arabic). Which of these requirements does it state, in any wording
or language? Only count a requirement if the tender clearly states it.

Requirements:
{listing}

Tender:
{tender}

Reply with a JSON list of the requirement IDs that are present, e.g. ["users", "odoo"], or [] if none."""


def build_flag_judge_prompt(issues: list[str], flags: dict) -> str:
    issue_list = "\n".join(f"- {i}" for i in issues)
    categories = "\n".join(f"- {name}: {meaning}" for name, meaning in flags.items())
    return f"""A procurement assistant raised these issues about a purchase request:
{issue_list}

Which of these problem categories do the issues describe? Only count a category if an issue clearly describes it.
{categories}

Reply with a JSON list of category names only, e.g. ["brand_lock"], or [] if none apply."""
