import json
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage

from kurrasa.config.prompts import build_baseline_prompt
from kurrasa.pipeline.run import load_scenario
from kurrasa.services.company import fill_template, load_facts, load_template, purchase_route


def parse_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        return None


def run_baseline(scenario: str, run_id: str, llm, out_root: Path = Path("results")) -> Path:
    """One Gemini call, no interview and no tools: the comparison point for the agent."""
    out = out_root / scenario / "baseline" / run_id
    out.mkdir(parents=True, exist_ok=True)
    facts = load_facts()
    opening = load_scenario(scenario)["opening_request"]

    reply = parse_json(llm.invoke([HumanMessage(content=build_baseline_prompt(opening, facts))]).text)
    package = {"requirements": {}, "issues": [], "sections": {}, "route": None,
               "questions_asked": 0, "stopped_reason": "bad_output"}

    if reply and isinstance(reply.get("sections"), dict):
        package["sections"] = reply["sections"]
        package["issues"] = [{"id": i, "description": d, "status": "open", "resolution": None}
                             for i, d in enumerate(reply.get("issues") or [], start=1)]
        if isinstance(reply.get("budget_sar"), int) and reply["budget_sar"] > 0:
            package["route"] = purchase_route(reply["budget_sar"], facts)
        try:
            tender = fill_template(load_template(), package["sections"], date.today(), f"SAHAB-{run_id}", facts)
            (out / "tender.txt").write_text(tender, encoding="utf-8")
            package["stopped_reason"] = "finished"
        except ValueError:
            pass   # missing sections: stays "bad_output"

    (out / "package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
