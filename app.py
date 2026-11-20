# Authored by Faris
"""LoreKeeper UI. Run it with:  streamlit run app.py

A chat-style interface over generation_engine.orchestrator.run_pipeline(). The page holds no
generation, retrieval or verification logic: it sends the user's message to the pipeline and
displays the PipelineResult it returns (see lorekeeper_ui/ for the presentation code).
"""

import streamlit as st

from generation_engine.models import DemoRequest
from generation_engine.orchestrator import run_pipeline
from lorekeeper_ui import components, shell
from lorekeeper_ui.theme import inject_css

st.set_page_config(
    page_title="LoreKeeper",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="auto",  # open on laptop/projector widths, collapsed on narrow screens
)
inject_css()

messages = st.session_state.setdefault("messages", [])

# A message comes from the composer or from a clicked suggestion card.
typed = st.chat_input("Describe a world, a character or the next scene…")
prompt = st.session_state.pop("pending_prompt", None) or typed
if prompt is not None and not prompt.strip():
    st.toast("Type a message to begin.", icon="✍️")
    prompt = None
if prompt:
    prompt = prompt.strip()
    messages.append({"role": "user", "content": prompt})

settings = shell.render_sidebar(messages)

if not messages:
    shell.render_welcome()
for index, message in enumerate(messages):
    components.render_message(index, message)

if prompt:
    request = DemoRequest(
        prompt=prompt, mode=settings.mode, max_repair_attempts=settings.max_repairs
    )
    with st.chat_message("assistant", avatar=components.ASSISTANT_AVATAR):
        with st.spinner("LoreKeeper is writing and checking your scene…"):
            try:
                reply = {"role": "assistant", "result": run_pipeline(request)}
            except Exception as error:  # show any pipeline failure instead of a stack trace
                reply = {"role": "assistant", "error": f"{type(error).__name__}: {error}"}
        messages.append(reply)
        components.render_reply(len(messages) - 1, reply)
