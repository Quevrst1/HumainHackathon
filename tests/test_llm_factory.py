from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from kurrasa.config.llm_factory import _TimeoutLLM


class RecordingModel(BaseChatModel):
    seen: list = []

    @property
    def _llm_type(self):
        return "recording"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(kwargs)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="x"))])

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=[t.name for t in tools], **kwargs)


@tool
def ask_requester(question: str) -> str:
    """Ask a question."""
    return "ok"


def test_bind_tools_passes_tools_to_inner_model():
    inner = RecordingModel()
    _TimeoutLLM(inner=inner).bind_tools([ask_requester]).invoke([HumanMessage(content="hi")])
    assert inner.seen[-1].get("tools") == ["ask_requester"]
