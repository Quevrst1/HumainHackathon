from kurrasa.config import AGENT_MODELS, create_llm

if __name__ == "__main__":
    # Smoke test until the scenario runner exists: proves keys, installs, and imports work.
    llm = create_llm(**AGENT_MODELS["agent"])
    print(llm.invoke("Reply with exactly: kurrasa online").content)
