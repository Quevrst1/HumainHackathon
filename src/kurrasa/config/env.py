import os

from dotenv import load_dotenv


class Env:
    def __init__(self):
        load_dotenv()
        self.GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
        self.DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY")
        self.NVIDIA_API_KEY     = os.getenv("NVIDIA_API_KEY")
        self.OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.APIFY_TOKEN        = os.getenv("APIFY_TOKEN")
