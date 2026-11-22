"""Conversation shell; no workflow selection or backend routing."""

import streamlit as st

from lorekeeper_ui.components import html, text
from lorekeeper_ui.theme import logo_html


def _new_session() -> None:
    st.session_state["messages"] = []
    st.session_state["active_scene_id"] = None
    st.session_state["pending_canon"] = None
    st.session_state["conversation"] = None
    st.session_state.pop("pending_prompt", None)


def render_sidebar(messages, world_id):
    with st.sidebar:
        html(
            f'<div class="lk-brand">{logo_html(34)}<div>'
            '<div class="lk-brand__name">LoreKeeper</div>'
            '<div class="lk-brand__tag">World archive</div></div></div>'
        )
        st.button("+ New chat", key="new_session", on_click=_new_session)
        st.caption(f"Active world: {world_id}")
        st.caption("Approved canon stays saved when you start a new chat. Conversation history lasts for this session.")


def render_welcome():
    html(
        '<div class="lk-welcome">'
        f"{logo_html(72, 'lk-welcome__logo')}"
        '<div class="lk-welcome__title">LoreKeeper</div>'
        '<div class="lk-welcome__tagline">Build worlds that remember.</div>'
        '<div class="lk-welcome__sub">Describe a character, write a scene, '
        'ask a question, or tell me what to change.</div></div>'
    )
    st.caption("Start by describing your world or a character. Character drafts become canon only when you approve them.")
