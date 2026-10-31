import json
from datetime import date
from pathlib import Path

import yaml

from kurrasa.agents.kurrasa import run_agent
from kurrasa.agents.requester import HumanRequester, SimulatedRequester
from kurrasa.services.company import load_facts, load_template
from kurrasa.services.events import EventLog, jsonl_listener, print_listener
from kurrasa.services.pdf import tender_pdf

SCENARIOS = Path(__file__).resolve().parents[3] / "scenarios"


def load_scenario(name: str) -> dict:
    return yaml.safe_load((SCENARIOS / name / "scenario.yaml").read_text(encoding="utf-8"))


def run_scenario(scenario: str | None, run_id: str, agent_llm, requester_llm,
                 out_root: Path = Path("results"), verbose: bool = True) -> Path:
    """Run the agent once (simulated requester, or a human when scenario is None) and save everything."""
    out = out_root / (scenario or "human") / "agent" / run_id
    out.mkdir(parents=True, exist_ok=True)

    events = EventLog()
    events.add_listener(jsonl_listener(out / "events.jsonl"))
    if verbose:
        events.add_listener(print_listener)

    requester = SimulatedRequester(load_scenario(scenario), requester_llm) if scenario else HumanRequester()
    package = run_agent(agent_llm, requester, events, load_facts(), load_template(), date.today(), f"SAHAB-{run_id}")

    save_package(out, package)
    return out


def save_package(out: Path, package: dict):
    """Write tender.txt (if finished), transcript.json and package.json for one run."""
    package = dict(package)
    tender = package.pop("tender")
    if tender:
        (out / "tender.txt").write_text(tender, encoding="utf-8")   # what the judges read
        (out / "tender.pdf").write_bytes(tender_pdf({**package, "tender": tender}))   # what people receive
    (out / "transcript.json").write_text(json.dumps(package.pop("transcript"), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
