# Gemma 4 through the Gemini API (free tier)
GEMINI = {"provider": "gemini", "model": "gemma-4-26b-a4b-it", "temperature": 0}

AGENT_MODELS = {
    "agent":     GEMINI,
    "requester": GEMINI,   # the simulated employee in the scenarios
}

# three different model families, none of them the agent's; majority vote
JUDGE_MODELS = [
    {"provider": "deepseek",   "model": "deepseek-chat", "temperature": 0},
    {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct", "temperature": 0},
    {"provider": "gemini",     "model": "gemini-3.5-flash-lite"},   # temperature can't be set
]

MAX_QUESTIONS = 10   # ask_requester calls per interview
MAX_STEPS = 60       # LLM calls per agent run
