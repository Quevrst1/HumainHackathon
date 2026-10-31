from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from kurrasa.agents.session import Message
from kurrasa.config.prompts import build_requester_prompt


class HumanRequester:
    """A person answering in the terminal. '/file <path>' attaches a file, '/done' ends the interview."""

    def __init__(self, input_fn=input):
        self.input_fn = input_fn

    def opening(self) -> Message:
        return self._read("What do you need? ")

    def reply(self, question: str) -> Message:
        return self._read(f"\nKurrasa: {question}\nYou: ")

    def _read(self, prompt: str) -> Message:
        attachments = []
        while True:
            line = self.input_fn(prompt).strip()
            if line == "/done":
                return Message(text="That's all I have.", attachments=attachments, done=True)
            if line.startswith("/file "):
                attachments.append(Path(line[6:].strip()))
                prompt = "(attached) "
                continue
            return Message(text=line, attachments=attachments)


class SimulatedRequester:
    """An LLM playing the employee described in a scenario.yaml."""

    def __init__(self, scenario: dict, llm):
        self.scenario = scenario
        self.llm = llm
        self.history = []

    def opening(self) -> Message:
        return Message(text=self.scenario["opening_request"])

    def reply(self, question: str) -> Message:
        self.history.append(HumanMessage(content=question))
        answer = self.llm.invoke([SystemMessage(content=build_requester_prompt(self.scenario)), *self.history])
        self.history.append(AIMessage(content=answer.text))
        return Message(text=answer.text)
