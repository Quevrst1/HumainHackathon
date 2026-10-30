"""Prompt builders. One build_*_prompt() function per role."""


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
