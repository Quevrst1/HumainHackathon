"""Default models and limits for the Kurrasa agent and its evaluation."""

GEMINI = {"provider": "gemini", "model": "gemini-2.5-flash", "temperature": 0}

AGENT_MODELS = {
    "agent":     GEMINI,   # the Kurrasa ReAct agent
    "requester": GEMINI,   # simulated requester persona (tests only)
    "baseline":  GEMINI,   # one-shot baseline for comparison
}

# Judge panel for evaluation; add other providers here once their keys are set up.
JUDGE_MODELS = [GEMINI]

MAX_QUESTIONS = 10   # ask_requester calls per interview
MAX_STEPS = 60       # LLM calls per agent run
