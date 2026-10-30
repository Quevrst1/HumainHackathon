import json
from datetime import date
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from kurrasa.agents.requester import SimulatedRequester
from kurrasa.config import MAX_QUESTIONS
from kurrasa.config.prompts import build_plain_chat_prompt
from kurrasa.pipeline.run import load_scenario
from kurrasa.services.company import fill_template, load_facts, load_template, purchase_route
from kurrasa.services.pdf import tender_pdf


def parse_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1]) if start != -1 else None
    except json.JSONDecodeError:
        return None


def run_plain_chat(scenario: str, run_id: str, llm, requester_llm, out_root: Path = Path("results")) -> Path:
    """Condition A: the same model chatting with the same requester, with no tools or procurement guidance."""
    out = out_root / scenario / "plain_chat" / run_id
    out.mkdir(parents=True, exist_ok=True)
    facts, today = load_facts(), date.today()
    requester = SimulatedRequester(load_scenario(scenario), requester_llm)

    opening = requester.opening().text
    transcript = [{"role": "requester", "text": opening, "attachments": []}]
    messages = [SystemMessage(content=build_plain_chat_prompt(facts, today)), HumanMessage(content=opening)]
    questions, forced, reply = 0, False, None

    while True:
        text = llm.invoke(messages).text
        messages.append(AIMessage(content=text))
        reply = parse_json(text)
        if reply and isinstance(reply.get("sections"), dict):
            break
        if questions < MAX_QUESTIONS:
            questions += 1
            answer = requester.reply(text).text
            transcript += [{"role": "agent", "text": text, "attachments": []},
                           {"role": "requester", "text": answer, "attachments": []}]
            messages.append(HumanMessage(content=answer))
        elif not forced:
            forced = True
            messages.append(HumanMessage(content="Question limit reached. Reply with the final JSON now."))
        else:
            reply = None
            break

    package = {"requirements": {}, "issues": [], "sections": {}, "route": None,
               "questions_asked": questions, "stopped_reason": "bad_output"}
    if reply:
        package["sections"] = reply["sections"]
        package["issues"] = [{"id": i, "description": d, "status": "open", "resolution": None}
                             for i, d in enumerate(reply.get("issues") or [], start=1)]
        if isinstance(reply.get("budget_sar"), int) and reply["budget_sar"] > 0:
            package["route"] = purchase_route(reply["budget_sar"], facts)
        try:
            tender = fill_template(load_template(), package["sections"], today, f"SAHAB-{run_id}", facts)
            (out / "tender.txt").write_text(tender, encoding="utf-8")
            (out / "tender.pdf").write_bytes(tender_pdf(tender))
            package["stopped_reason"] = "finished"
        except ValueError:
            pass   # missing sections: stays "bad_output"

    (out / "transcript.json").write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
