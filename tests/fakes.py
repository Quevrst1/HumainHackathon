from langchain_core.messages import AIMessage

from kurrasa.agents.session import Message
from kurrasa.services.company import AGENT_BLANKS


class ScriptedLLM:
    def __init__(self, replies, repeat_last=False):
        self.replies = list(replies)
        self.repeat_last = repeat_last
        self.received = []
        self.bound = []

    def bind_tools(self, tools):
        self.bound.append({t.name for t in tools})
        return self

    def invoke(self, messages):
        self.received.append(list(messages))
        if self.repeat_last and len(self.replies) == 1:
            return self.replies[0]
        return self.replies.pop(0)


class StubRequester:
    def __init__(self, replies=()):
        self.replies = list(replies)

    def opening(self):
        return Message(text="We need a CRM.")

    def reply(self, question):
        return self.replies.pop(0) if self.replies else Message(text="ok")


def call(name, args, i=0):
    return {"name": name, "args": args, "id": f"{name}-{i}"}


def finishing_script():
    writes = [call("write_section", {"name": b, "text": f"نص {b}"}, i) for i, b in enumerate(AGENT_BLANKS)]
    return [
        AIMessage(content="", tool_calls=[call("ask_requester", {"question": "How many users?"})]),
        AIMessage(content="", tool_calls=[call("next_stage", {})]),
        AIMessage(content="", tool_calls=[call("purchase_route", {"budget_sar": 900_000})]),
        AIMessage(content="", tool_calls=[call("next_stage", {}, 1)]),
        AIMessage(content="", tool_calls=writes),
        AIMessage(content="", tool_calls=[call("finish", {})]),
    ]
