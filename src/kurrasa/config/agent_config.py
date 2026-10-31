"""Default models and limits for the Kurrasa agent and its evaluation."""

# Gemma 4 via the Gemini API: free tier, native tool calling, fast (mixture-of-experts, 4B active)
GEMINI = {"provider": "gemini", "model": "gemma-4-26b-a4b-it", "temperature": 0}

AGENT_MODELS = {
    "agent":     GEMINI,   # the Kurrasa ReAct agent
    "requester": GEMINI,   # simulated requester persona (tests only)
}

# Judge panel: three model families, none of them the agent's model (so none grades its own writing).
# Decisions are a 2-of-3 majority vote.
JUDGE_MODELS = [
    {"provider": "deepseek",   "model": "deepseek-chat", "temperature": 0},
    {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct", "temperature": 0},
    {"provider": "gemini",     "model": "gemini-3.5-flash-lite"},   # fixed sampling: temperature not settable
]

MAX_QUESTIONS = 10   # ask_requester calls per interview
MAX_STEPS = 60       # LLM calls per agent run
