import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult

from kurrasa.config.env import Env

LLM_HARD_TIMEOUT = 120   # seconds per attempt
LLM_MAX_RETRIES  = 3     # max retries per call
LLM_RETRY_DELAY  = 30    # seconds between retries
LLM_HTTP_TIMEOUT = 90    # per-client HTTP timeout


def _with_timeout_and_retry(fn, *args, **kwargs):
    """
    Run fn with a hard timeout, retrying up to LLM_MAX_RETRIES times.

    Args:
        fn:       Callable to invoke (typically an LLM _generate method).
        *args:    Positional arguments forwarded to fn.
        **kwargs: Keyword arguments forwarded to fn.

    Returns:
        Whatever fn returns on success; raises the last error after all retries.
    """
    last_error = None
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=LLM_HARD_TIMEOUT)
        except FuturesTimeoutError:
            last_error = TimeoutError(f"LLM call timed out after {LLM_HARD_TIMEOUT}s (attempt {attempt}/{LLM_MAX_RETRIES})")
            print(f"  LLM timeout on attempt {attempt}/{LLM_MAX_RETRIES} — {'retrying...' if attempt < LLM_MAX_RETRIES else 'giving up'}")
            if attempt < LLM_MAX_RETRIES:
                time.sleep(LLM_RETRY_DELAY)
        except Exception as e:
            last_error = e
            print(f"  LLM error on attempt {attempt}/{LLM_MAX_RETRIES}: {e} — {'retrying...' if attempt < LLM_MAX_RETRIES else 'giving up'}")
            if attempt < LLM_MAX_RETRIES:
                # Honour API-suggested delay on rate limits
                m = re.search(r'retry in (\d+(?:\.\d+)?)s', str(e))
                time.sleep(float(m.group(1)) + 5 if m else LLM_RETRY_DELAY)
        finally:
            executor.shutdown(wait=False)
    raise last_error


class _TimeoutLLM(BaseChatModel):
    """Wraps any BaseChatModel with a hard timeout and automatic retry."""
    inner: object

    class Config:
        arbitrary_types_allowed = True

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return _with_timeout_and_retry(self.inner._generate, messages, stop=stop, run_manager=run_manager, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "timeout-wrapped"

    def bind_tools(self, tools, **kwargs):
        return _TimeoutLLM(inner=self.inner.bind_tools(tools, **kwargs))


# Default model per provider
DEFAULT_MODELS = {
    "gemini":     "gemini-2.5-flash",
    "ollama":     "qwen2.5:14b",
    "openrouter": "meta-llama/llama-3.3-70b-instruct",
    "deepseek":   "deepseek-chat",
    "nvidia":     "qwen/qwen2.5-coder-32b-instruct",
}

# OpenAI-compatible providers: provider -> (base_url, Env attribute holding the key).
# Adding one (e.g. a HUMAIN endpoint) is a single line here plus a DEFAULT_MODELS entry.
OPENAI_COMPATIBLE = {
    "openrouter": ("https://openrouter.ai/api/v1",         "OPENROUTER_API_KEY"),
    "deepseek":   ("https://api.deepseek.com/v1",          "DEEPSEEK_API_KEY"),
    "nvidia":     ("https://integrate.api.nvidia.com/v1",  "NVIDIA_API_KEY"),
}


def create_llm(provider: str = "gemini", model: str = None, temperature: float = None) -> BaseChatModel:
    """
    Build a LangChain chat model for the requested provider.

    Args:
        provider:    Provider key (gemini, ollama, or any key in OPENAI_COMPATIBLE).
        model:       Model name override. Falls back to DEFAULT_MODELS[provider].
        temperature: Sampling temperature; None leaves the provider default.

    Returns:
        Configured BaseChatModel, wrapped with timeout/retry.
    """
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
