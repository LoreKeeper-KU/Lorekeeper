# Authored by Faris
"""LoreKeeper UI. Run it with:  streamlit run app.py

A chat-style interface over generation_engine.orchestrator.run_pipeline(). The page holds no
generation, retrieval or verification logic: it sends the user's message to the pipeline and
displays the PipelineResult it returns (see lorekeeper_ui/ for the presentation code).
"""

import json
import os

from pathlib import Path
from threading import RLock

import streamlit as st
from dotenv import load_dotenv


# Use the main repository for database and image paths.
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
load_dotenv(ROOT / ".env")


from generation_engine.models import DemoRequest
from generation_engine.team_demo import _serialize
from generation_engine.ui_backend import (
    NoCanonError,
    retrieve_for_request,
    run_ui_request,
)

from shared.ai_client import AIClient

from lorekeeper_ui import components, shell
from lorekeeper_ui.theme import inject_css


st.set_page_config(
    page_title="LoreKeeper",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="auto",
)

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


def render_reply(index, message):
    """Display a saved result without generating it again."""

    if "error" in message:
        st.error(message["error"])
        return

    team = message.get("team_result")

    if team is None:
        # Support earlier messages from the original UI.
        components.render_reply(index, message)
        return

    # Reuse Faris's text, verification and repair-history display.
    components.render_result(
        index,
        team.text,
        show_artwork=False,
    )

    if team.asset:
        st.markdown("**Concept artwork**")

        image_path = Path(team.asset.image_path)

        if not image_path.is_absolute():
            image_path = ROOT / image_path

        if image_path.is_file():
            st.image(str(image_path))
        else:
            st.warning(
                "The saved image file is no longer available."
            )

    status = team.visual_status

    if status == "no_mismatches_detected":
        st.success(
            "Artwork check: no mismatches detected."
        )

    elif status == "needs_review":
        st.warning(
            "Artwork needs review. Some facts conflict "
            "or could not be assessed."
        )

    elif status == "skipped_text_needs_review":
        st.info(
            "Artwork was skipped because the text needs review."
        )

    elif status == "error":
        st.error(
            team.visual_error
            or "Artwork could not be completed."
        )

    else:
        st.caption(
            "Artwork was not requested for this scene."
        )

    if team.visual_report or team.visual_checks:
        with st.expander("View artwork checks"):
            st.write(
                "Image repair attempts:",
                team.visual_repair_attempts,
            )

            for reason in team.visual_review_reasons:
                st.write(reason)

            if team.visual_checks:
                st.dataframe(
                    [
                        check.model_dump(mode="json")
                        for check in team.visual_checks.checks
                    ],
                    use_container_width=True,
                )

    with st.expander("View canon used for this scene"):
        if team.canon_facts:
            st.dataframe(
                [
                    fact.model_dump(mode="json")
                    for fact in team.canon_facts
                ],
                use_container_width=True,
            )
        else:
            st.caption(
                "This scene was generated without canon."
            )

    # Downloading the report does not generate another scene.
    st.download_button(
        "Download scene report",
        data=json.dumps(
            _serialize(team),
            indent=2,
            ensure_ascii=False,
        ),
        file_name=f"lorekeeper_scene_{index}.json",
        mime="application/json",
        key=f"download-report-{index}",
    )


# Keep completed results in this browser session.
messages = st.session_state.setdefault("messages", [])

typed = st.chat_input(
    "Describe a scene involving Amina or the Northern Kingdom…"
)

prompt = (
    st.session_state.pop("pending_prompt", None)
    or typed
)

if prompt is not None:
    prompt = prompt.strip()

    if not prompt:
        st.toast(
            "Type a message to begin.",
            icon="✍️",
        )
        prompt = None

if prompt:
    messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )


settings = shell.render_sidebar(messages)

with st.sidebar:
    include_visuals = st.checkbox(
        "Generate artwork",
        value=True,
        key="include_visuals",
        disabled=settings.mode != "verified",
    )

    max_visual_repairs = st.slider(
        "Image repair limit",
        0,
        3,
        1,
        key="max_visual_repairs",
        disabled=(
            not include_visuals
            or settings.mode != "verified"
        ),
    )

    st.caption(
        "Artwork runs after text passes its checks. "
        "Generation uses your API account."
    )


if not messages:
    shell.render_welcome()

    st.caption(
        "This demo generates individual scenes from existing canon. "
        "Mention Amina or the Northern Kingdom. "
        "Chat history is not yet story memory."
    )


# Redisplay previous messages using their saved results.
for index, message in enumerate(messages):
    if message["role"] == "user":
        components.render_message(index, message)

    else:
        with st.chat_message(
            "assistant",
            avatar=components.ASSISTANT_AVATAR,
        ):
            render_reply(index, message)


# Only a newly submitted prompt runs the backend.
# Changing settings or opening reports does not regenerate content.
if prompt:
    request = DemoRequest(
        prompt=prompt,
        mode=settings.mode,
        max_repair_attempts=settings.max_repairs,
    )

    with st.chat_message(
        "assistant",
        avatar=components.ASSISTANT_AVATAR,
    ):
        with st.spinner(
            "LoreKeeper is creating and checking your scene…"
        ):
            try:
                # Retrieve before loading the model or making API calls.
                facts = retrieve_for_request(request)
                client = AIClient()

                comparator = (
                    load_comparator()
                    if request.mode == "verified"
                    else None
                )

                team = run_ui_request(
                    request,
                    facts,
                    client,
                    comparator=comparator,
                    include_visuals=(
                        include_visuals
                        and request.mode == "verified"
                    ),
                    max_visual_repairs=max_visual_repairs,
                )

                reply = {
                    "role": "assistant",
                    "team_result": team,
                }

            except NoCanonError as error:
                reply = {
                    "role": "assistant",
                    "error": str(error),
                }

            except Exception as error:
                # Avoid displaying raw provider responses or secrets.
                reply = {
                    "role": "assistant",
                    "error": (
                        "The request could not complete "
                        f"({type(error).__name__}). "
                        "Check the local model, API configuration "
                        "and account access."
                    ),
                }

        messages.append(reply)

        render_reply(
            len(messages) - 1,
            reply,
        )