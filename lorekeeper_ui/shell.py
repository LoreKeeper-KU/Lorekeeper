# Authored by Faris
"""The application shell around the conversation: sidebar and welcome state."""

from dataclasses import dataclass

import streamlit as st

from lorekeeper_ui.components import html, text
from lorekeeper_ui.presentation import session_title
from lorekeeper_ui.theme import logo_html

# Pipeline modes understood by run_pipeline(), shown only under Advanced Settings.
MODE_LABELS = {
    "verified": "Verified (recommended)",
    "rag": "Canon-aware, no check",
    "basic": "Generate only",
}
DEFAULT_MAX_REPAIRS = 3

# SUGGESTIONS = (
#     ("Create a fantasy kingdom", ":material/castle:",
#      "Shape its history, rulers and lands",
#      "Create a fantasy kingdom with its history, rulers and geography."),
#     ("Define a character", ":material/person:",
#      "Give them a past, a goal and a flaw",
#      "Define a character for my world, with their background, goals and flaws."),
#     ("Write the next scene", ":material/auto_stories:",
#      "Continue the story, in line with canon",
#      "Write the next scene of my story."),
#     ("Check my world's canon", ":material/verified_user:",
#      "Look for contradictions in what is established",
#      "Check my world's canon for contradictions."),
# )

SUGGESTIONS = (
    (
        "Describe Amina",
        ":material/person:",
        "Use her established appearance",
        "Describe only Amina's black hair and brown eyes in two "
        "short factual sentences. Do not add actions, scenery, "
        "magic, or other details.",
    ),
    (
        "A market scene",
        ":material/storefront:",
        "Place Amina in the Northern Kingdom",
        "Write a short scene about Amina visiting a market "
        "in the Northern Kingdom.",
    ),
    (
        "A castle scene",
        ":material/castle:",
        "Write a scene using existing canon",
        "Write a short scene about Amina at a castle "
        "in the Northern Kingdom.",
    ),
    (
        "Describe the ruler",
        ":material/auto_stories:",
        "Describe Amina using approved facts",
        "Write two factual sentences describing Amina "
        "using only the approved canon.",
    ),
)


@dataclass(frozen=True)
class Settings:
    mode: str
    max_repairs: int


def _new_session() -> None:
    st.session_state["messages"] = []
    st.session_state.pop("pending_prompt", None)


def _choose(prompt: str) -> None:
    st.session_state["pending_prompt"] = prompt


def _section(label: str) -> None:
    html(f'<div class="lk-section-label">{text(label)}</div>')


def render_sidebar(messages: list) -> Settings:
    with st.sidebar:
        html(
            f'<div class="lk-brand">{logo_html(34)}<div>'
            '<div class="lk-brand__name">LoreKeeper</div>'
            '<div class="lk-brand__tag">World archive</div></div></div>'
        )
        st.button("+ New Session", key="new_session", on_click=_new_session)

        _section("Worlds")
        html(
            '<div class="lk-nav-item lk-nav-item--active">Demo World</div>'
            '<div class="lk-nav-hint">Saved worlds will appear here once persistence is connected.</div>'
        )

        _section("Scenes")
        titles = [session_title(m["content"]) for m in messages if m["role"] == "user"]
        if titles:
            html("".join(f'<div class="lk-nav-item">{text(title)}</div>' for title in titles))
        else:
            html('<div class="lk-nav-hint">No scenes yet</div>')

        with st.container(key="sidebar-settings"):
            with st.expander("Advanced Settings", expanded=False):
                st.caption("Technical options. LoreKeeper normally runs the full verified pipeline.")
                mode = st.selectbox(
                    "Pipeline", list(MODE_LABELS), format_func=MODE_LABELS.get, key="mode"
                )
                max_repairs = st.slider(
                    "Max repair attempts", 0, 5, DEFAULT_MAX_REPAIRS, key="max_repairs"
                )
    return Settings(mode=mode, max_repairs=max_repairs)


def render_welcome() -> None:
    html(
        '<div class="lk-welcome">'
        f"{logo_html(72, 'lk-welcome__logo')}"
        '<div class="lk-welcome__title">LoreKeeper</div>'
        '<div class="lk-welcome__tagline">Build worlds that remember.</div>'
        '<div class="lk-welcome__sub">Create characters, expand lore, generate scenes '
        "and keep your world consistent.</div></div>"
    )
    columns = st.columns(2)
    for position, (title, icon, blurb, prompt) in enumerate(SUGGESTIONS):
        with columns[position % 2]:
            st.button(
                f"{title}\n\n{blurb}",
                key=f"suggest_{position}",
                icon=icon,
                on_click=_choose,
                args=(prompt,),
            )
