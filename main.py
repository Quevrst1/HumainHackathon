from kurrasa.config import create_llm

# Which scenario folder under scenarios/ to run, and which phase.
SCENARIO = "crm_vague"
PHASE    = 1

# Per-role LLMs; overrides the defaults in config/agent_config.py.
AGENT_MODELS = {
    "interviewer": {"provider": "gemini", "model": "gemini-2.5-flash"},
    "drafter":     {"provider": "gemini", "model": "gemini-2.5-flash"},
    "requester":   {"provider": "gemini", "model": "gemini-2.5-flash"},
    "judge":       {"provider": "gemini", "model": "gemini-2.5-flash"},
}


if __name__ == "__main__":
    # Smoke test until the phase 1 pipeline exists: proves keys, installs, and imports work.
    llm = create_llm(**AGENT_MODELS["interviewer"])
    print(llm.invoke("Reply with exactly: kurrasa online").content)
