import os

from dotenv import load_dotenv


class Env:
    def __init__(self):
        load_dotenv()
        self.GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
        self.DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY")
        self.APIFY_TOKEN        = os.getenv("APIFY_TOKEN")
