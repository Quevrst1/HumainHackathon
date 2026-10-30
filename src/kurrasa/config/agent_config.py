"""Default models and limits for the Kurrasa agent and its evaluation."""

# Gemma 4 via the Gemini API: free tier, native tool calling, fast (mixture-of-experts, 4B active)
GEMINI = {"provider": "gemini", "model": "gemma-4-26b-a4b-it", "temperature": 0}

AGENT_MODELS = {
    "agent":     GEMINI,   # the Kurrasa ReAct agent
    "requester": GEMINI,   # simulated requester persona (tests only)
}

# Judge panel: a different model from the agent, so it isn't grading its own writing.
# Add other providers here once their keys are set up.
JUDGE_MODELS = [{"provider": "gemini", "model": "gemini-3.5-flash-lite"}]

MAX_QUESTIONS = 10   # ask_requester calls per interview
MAX_STEPS = 60       # LLM calls per agent run
