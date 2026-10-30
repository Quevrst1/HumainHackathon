import html
from datetime import datetime
from pathlib import Path

import streamlit as st

from kurrasa.config import AGENT_MODELS, create_llm
from kurrasa.services.company import load_facts
from kurrasa.ui.bridge import AgentRunner

STAGES = ["request", "interview", "checks", "draft", "package"]
UPLOADS = Path("results") / "uploads"

st.set_page_config(page_title="Kurrasa", layout="wide")
st.title("Kurrasa")
st.caption("AI procurement agent for Sahab")


def save_uploads(files) -> list[Path]:
    folder = UPLOADS / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in files or []:
        path = folder / f.name
        path.write_bytes(f.getvalue())
        paths.append(path)
    return paths


@st.fragment(run_every=1.5)
def chat_panel(runner: AgentRunner):
    for message in runner.chat():
        with st.chat_message("user" if message["role"] == "requester" else "assistant"):
            st.write(message["text"])

    if runner.error:
        st.error(f"Kurrasa stopped: {runner.error}")
    elif runner.done:
        st.success("Done. The package is in the Review tab.")
    elif runner.pending_question():
        reply = st.chat_input("Your answer", accept_file="multiple")
        if reply:
            runner.answer(reply.text or "", save_uploads(reply.files))
            st.rerun(scope="fragment")
    else:
        st.caption("Kurrasa is working…")


@st.fragment(run_every=1.5)
def status_panel(runner: AgentRunner):
    events = runner.events.events
    current = "package" if runner.done else (events[-1].stage if events else "request")
    st.markdown("  →  ".join(f"**{s.upper()}**" if s == current else s for s in STAGES))
    if runner.pending_question():
        st.info("Waiting for your answer in the Request tab.")
    for e in events:
        st.write(f"`{e.time[11:19]}` · **{e.stage}** · {e.summary}")


@st.fragment(run_every=2)
def review_panel(runner: AgentRunner):
    if not runner.done:
        st.caption("The package appears here when Kurrasa finishes.")
        return
    package = runner.package or {}
    if package.get("stopped_reason") != "finished":
        st.warning(f"Kurrasa did not finish ({package.get('stopped_reason') or runner.error}).")

    route = package.get("route") or {}
    left, right = st.columns(2)
    left.metric("Purchasing method", route.get("method", "—"))
    right.metric("Approver", route.get("approver", "—"))

    st.subheader("Issues")
    issues = package.get("issues") or []
    if not issues:
        st.write("No issues raised.")
    for issue in issues:
        mark = "✅ resolved" if issue["status"] == "resolved" else "⚠️ open"
        st.write(f"{mark} · {issue['description']}" + (f" → {issue['resolution']}" if issue["resolution"] else ""))

    if package.get("tender"):
        st.subheader("Tender (كراسة الشروط والمواصفات)")
        st.download_button("Download tender", package["tender"], file_name="tender.txt")
        st.markdown(f'<div dir="rtl" style="white-space: pre-wrap; text-align: right">{html.escape(package["tender"])}</div>',
                    unsafe_allow_html=True)


runner: AgentRunner | None = st.session_state.get("runner")
request_tab, status_tab, review_tab = st.tabs(["Request", "Status", "Review"])

with request_tab:
    if runner is None:
        with st.form("request"):
            department = st.selectbox("Department", list(load_facts()["departments"]))
            need = st.text_area("What do you need?")
            budget = st.number_input("Budget (SAR)", min_value=0, step=1000)
            files = st.file_uploader("Attachments (optional)", accept_multiple_files=True)
            if st.form_submit_button("Send to procurement"):
                if not need.strip() or budget <= 0:
                    st.error("Please describe what you need and give a budget.")
                else:
                    runner = AgentRunner(create_llm(**AGENT_MODELS["agent"]))
                    runner.start(department, need.strip(), int(budget), save_uploads(files))
                    st.session_state.runner = runner
                    st.rerun()
    else:
        chat_panel(runner)
        if st.button("New request"):
            del st.session_state["runner"]
            st.rerun()

with status_tab:
    if runner:
        status_panel(runner)
    else:
        st.caption("Submit a request to see Kurrasa's progress.")

with review_tab:
    if runner:
        review_panel(runner)
    else:
        st.caption("Nothing to review yet.")
