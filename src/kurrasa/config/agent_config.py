"""Default agent-specific configuration.

These values are fallbacks: `main.py` passes explicit `agent_models`
to the pipeline, which override the defaults here.

Supported providers: "gemini", "ollama", "openrouter", "deepseek",
"nvidia" (see kurrasa.config.create_llm).
"""

# Max interview turns before the agent must draft the tender (phase 1).
MAX_INTERVIEW_TURNS = 8

# Per-role LLM defaults. `model: None` means use the provider's default.
AGENT_MODELS = {
    "interviewer": {"provider": "gemini", "model": None},  # asks the requester follow-up questions
    "drafter":     {"provider": "gemini", "model": None},  # writes the tender document
    "requester":   {"provider": "gemini", "model": None},  # simulated requester persona (test only)
    "judge":       {"provider": "gemini", "model": None},  # scores hidden-requirement recovery
}
