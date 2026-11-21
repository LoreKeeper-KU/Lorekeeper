"""LoreKeeper chat UI. Run with: streamlit run app.py.

The UI passes messages and conversation context to the backend. Workflow
selection, canon retrieval, creation, and verification belong to the backend.
"""

import os
from pathlib import Path
from threading import RLock

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
load_dotenv(ROOT / ".env")

from generation_engine.models import ChatMessage, ChatRequest
from generation_engine.ui_backend import handle_message
from lorekeeper_ui import components, shell
from lorekeeper_ui.theme import inject_css

st.set_page_config(page_title="LoreKeeper", page_icon="🛡️", layout="wide")
inject_css()


@st.cache_resource(show_spinner=False)
def load_comparator():
    """Load the NLI model once per server process."""

    from continuity_checker.nli_comparator import (
        NLIComparator,
    )

    model = NLIComparator.from_pretrained(
        "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    )

    lock = RLock()

    # The cached model is shared between browser sessions.
    # Protect model access when requests arrive simultaneously.
    def compare(claim, fact):
        with lock:
            return model(claim, fact)

    return compare

# Discard only incompatible session objects left by the old scene-only UI.
if st.session_state.get("chat_schema") != 1:
    st.session_state["messages"] = []
    st.session_state["active_scene_id"] = None
    st.session_state["pending_canon"] = None
    st.session_state["chat_schema"] = 1

world_id = st.session_state.setdefault("world_id", "world_001")
if st.session_state.get("conversation_world", world_id) != world_id:
    shell._new_session()
st.session_state["conversation_world"] = world_id
messages = st.session_state.setdefault("messages", [])
shell.render_sidebar(messages, world_id)
# A New chat callback can replace the list before this run.
messages = st.session_state["messages"]

if not messages:
    shell.render_welcome()

for index, message in enumerate(messages):
    components.render_chat_message(index, message)

prompt = st.chat_input("Message LoreKeeper…")
if prompt and prompt.strip():
    request = ChatRequest(
        message=prompt.strip(), world_id=world_id,
        history=list(messages),
        active_scene_id=st.session_state.get("active_scene_id"),
        pending_canon=st.session_state.get("pending_canon"),
    )
    user_message = ChatMessage(role="user", content=request.message, world_id=world_id)
    messages.append(user_message)
    components.render_chat_message(len(messages) - 1, user_message)

    try:
        with st.spinner("Thinking…"):
            reply = handle_message(request, comparator_factory=load_comparator)
        st.session_state["active_scene_id"] = reply.active_scene_id
        st.session_state["pending_canon"] = reply.pending_canon
        assistant_message = reply.message
    except Exception as error:
        # Provider responses can contain secrets. Preserve context for retries
        # without exposing raw errors or pretending generation succeeded.
        assistant_message = ChatMessage(
            role="assistant", world_id=world_id, kind="error",
            content=f"I couldn't complete that request ({type(error).__name__}). "
                    "Check the API or local model configuration, then try again.",
        )
    messages.append(assistant_message)
    components.render_chat_message(len(messages) - 1, assistant_message)
