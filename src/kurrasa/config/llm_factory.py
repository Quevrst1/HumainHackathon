import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult
from pydantic import ConfigDict

from kurrasa.config.env import Env

LLM_HARD_TIMEOUT = 120   # seconds per attempt
LLM_MAX_RETRIES  = 3     # max retries per call
LLM_RETRY_DELAY  = 30    # seconds between retries
LLM_HTTP_TIMEOUT = 90    # per-client HTTP timeout


def _with_timeout_and_retry(fn, *args, **kwargs):
    """Call fn with a hard timeout; retry on timeouts and API errors."""
    last_error = None
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=LLM_HARD_TIMEOUT)
        except FuturesTimeoutError:
            last_error = TimeoutError(f"LLM call timed out after {LLM_HARD_TIMEOUT}s (attempt {attempt}/{LLM_MAX_RETRIES})")
            print(f"    model timed out after {LLM_HARD_TIMEOUT}s, {'retrying' if attempt < LLM_MAX_RETRIES else 'giving up'}", flush=True)
            if attempt < LLM_MAX_RETRIES:
                time.sleep(LLM_RETRY_DELAY)
        except Exception as e:
            last_error = e
            # wait as long as the API asks to on rate limits
            m = re.search(r'retry in (\d+(?:\.\d+)?)s', str(e))
            delay = float(m.group(1)) + 5 if m else LLM_RETRY_DELAY
            reason = "rate limit" if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) else str(e).splitlines()[0][:80]
            if attempt < LLM_MAX_RETRIES:
                print(f"    {reason}, waiting {delay:.0f}s", flush=True)
                time.sleep(delay)
            else:
                print(f"    {reason}, giving up", flush=True)
        finally:
            executor.shutdown(wait=False)
    raise last_error


class _TimeoutLLM(BaseChatModel):
    """Any chat model, with a hard timeout and retries."""
    inner: object
    bound: dict = {}   # tool definitions from bind_tools

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return _with_timeout_and_retry(self.inner._generate, messages, stop=stop, run_manager=run_manager, **{**self.bound, **kwargs})

    @property
    def _llm_type(self) -> str:
        return "timeout-wrapped"

    def bind_tools(self, tools, **kwargs):
        # wrapping the bound model would drop the tools, so keep its kwargs instead
        return _TimeoutLLM(inner=self.inner, bound=self.inner.bind_tools(tools, **kwargs).kwargs)


DEFAULT_MODELS = {
    "gemini":     "gemma-4-26b-a4b-it",
    "ollama":     "qwen2.5:14b",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "deepseek":   "deepseek-chat",
    "nvidia":     "qwen/qwen2.5-coder-32b-instruct",
}

# provider -> (base url, name of the key in .env)
OPENAI_COMPATIBLE = {
    "openrouter": ("https://openrouter.ai/api/v1",         "OPENROUTER_API_KEY"),
    "deepseek":   ("https://api.deepseek.com/v1",          "DEEPSEEK_API_KEY"),
    "nvidia":     ("https://integrate.api.nvidia.com/v1",  "NVIDIA_API_KEY"),
}


def create_llm(provider: str = "gemini", model: str = None, temperature: float = None) -> BaseChatModel:
    env = Env()
    model_name = model or DEFAULT_MODELS[provider]
    extra = {} if temperature is None else {"temperature": temperature}

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return _TimeoutLLM(inner=ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=env.GEMINI_API_KEY,
            request_timeout=LLM_HTTP_TIMEOUT,
            **extra,
        ))

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return _TimeoutLLM(inner=ChatOllama(model=model_name, base_url=env.OLLAMA_BASE_URL, **extra))

    if provider in OPENAI_COMPATIBLE:
        from langchain_openai import ChatOpenAI
        base_url, key_attr = OPENAI_COMPATIBLE[provider]
        return _TimeoutLLM(inner=ChatOpenAI(
            model=model_name,
            api_key=getattr(env, key_attr),
            base_url=base_url,
            timeout=LLM_HTTP_TIMEOUT,
            **extra,
        ))

    raise ValueError(f"Unknown provider '{provider}'. Choose from: gemini, ollama, {', '.join(OPENAI_COMPATIBLE)}.")
