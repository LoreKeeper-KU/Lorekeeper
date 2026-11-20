# Authored by Faris
"""The chat-style Streamlit UI, driven with a fake run_pipeline that returns real result types.

The UI is built against generation_engine.orchestrator.run_pipeline only, so these tests
inject their own pipeline results instead of depending on what the current mock returns.
"""

import base64
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from generation_engine.models import DemoRequest
from ui_builders import (
    CONTRADICTION,
    NEW_ADDITION,
    ORIGINAL,
    REPAIRED,
    SUPPORTED,
    UNCERTAIN,
    FakePipeline,
    assessment,
    result,
)
from shared.schemas import ClaimClassification

APP = Path(__file__).resolve().parents[2] / "app.py"
WELCOME_TAGLINE = "Build worlds that remember."
SUGGESTIONS = [
    "Create a fantasy kingdom",
    "Define a character",
    "Write the next scene",
    "Check my world's canon",
]
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

REPAIRED_RESULT = [[CONTRADICTION], [SUPPORTED]]


@pytest.fixture
def launch(monkeypatch):
    """Start the app with a fake pipeline; returns (AppTest, FakePipeline)."""

    def start(outcome):
        fake = FakePipeline(outcome)
        monkeypatch.setattr("generation_engine.orchestrator.run_pipeline", fake)
        return AppTest.from_file(str(APP), default_timeout=10).run(), fake

    return start


def send(at, text="A siege at Silverkeep."):
    return at.chat_input[0].set_value(text).run()


def markdown_values(elements):
    return [element.value for element in elements.markdown]


def page_text(at):
    """The page's markdown, minus the injected stylesheet (its text names every CSS class)."""
    return "\n".join(
        value for value in markdown_values(at) if not value.lstrip().startswith("<style>")
    )


def expander(at, label):
    matches = [item for item in at.expander if item.label == label]
    assert matches, f"no expander labelled {label!r}; found {[e.label for e in at.expander]}"
    return matches[0]


def images(at):
    """Image elements; AppTest names them "imgs" in older Streamlit and "image" in newer."""
    return [*at.get("image"), *at.get("imgs")]


def has_expander(at, label):
    return any(item.label == label for item in at.expander)


# ---- the welcome state and the shell ----

def test_before_the_first_message_a_welcome_with_four_suggestions_is_shown(launch):
    at, fake = launch(result([[SUPPORTED]]))

    assert not at.exception
    assert WELCOME_TAGLINE in page_text(at)
    assert "Create characters, expand lore, generate scenes" in page_text(at)
    labels = [button.label for button in at.main.button]
    for suggestion in SUGGESTIONS:
        assert any(suggestion in label for label in labels)
    assert not at.chat_message
    assert fake.requests == []


def test_the_sidebar_has_branding_new_session_worlds_scenes_and_settings(launch):
    at, _ = launch(result([[SUPPORTED]]))

    sidebar_text = "\n".join(markdown_values(at.sidebar))
    assert "LoreKeeper" in sidebar_text
    assert "Worlds" in sidebar_text
    assert "Scenes" in sidebar_text
    assert "No scenes yet" in sidebar_text
    assert at.sidebar.button(key="new_session").label.startswith("+")
    settings = [item for item in at.sidebar.expander if item.label == "Advanced Settings"]
    assert len(settings) == 1 and settings[0].proto.expanded is False


def test_developer_controls_live_only_under_collapsed_advanced_settings(launch):
    at, _ = launch(result([[SUPPORTED]]))

    assert len(at.main.selectbox) == 0 and len(at.main.slider) == 0
    assert at.selectbox(key="mode").value == "verified"
    assert at.slider(key="max_repairs").value == 3


def test_the_composer_is_a_chat_input(launch):
    at, _ = launch(result([[SUPPORTED]]))

    assert len(at.chat_input) == 1
    assert at.chat_input[0].placeholder


# ---- sending messages ----

def test_a_typed_message_runs_the_verified_pipeline_by_default(launch):
    at, fake = launch(result(REPAIRED_RESULT))

    send(at, "  A siege at Silverkeep.  ")

    assert fake.requests == [
        DemoRequest(prompt="A siege at Silverkeep.", mode="verified", max_repair_attempts=3)
    ]


def test_advanced_settings_change_the_pipeline_request(launch):
    at, fake = launch(result(REPAIRED_RESULT))

    at.selectbox(key="mode").select("rag")
    at.slider(key="max_repairs").set_value(1)
    send(at)

    assert fake.requests[0].mode == "rag"
    assert fake.requests[0].max_repair_attempts == 1


def test_clicking_a_suggestion_runs_it_and_leaves_the_welcome_state(launch):
    at, fake = launch(result(REPAIRED_RESULT))

    at.button(key="suggest_0").click().run()

    assert len(fake.requests) == 1
    assert "fantasy kingdom" in fake.requests[0].prompt.lower()
    assert fake.requests[0].mode == "verified"
    assert WELCOME_TAGLINE not in page_text(at)
    assert [message.name for message in at.chat_message] == ["user", "assistant"]


def test_whitespace_only_input_is_ignored(launch):
    at, fake = launch(result(REPAIRED_RESULT))

    send(at, "   ")

    assert fake.requests == []
    assert not at.chat_message
    assert WELCOME_TAGLINE in page_text(at)


def test_the_conversation_shows_the_user_message_then_the_assistant_scene(launch):
    at, _ = launch(result(REPAIRED_RESULT))

    send(at, "A siege at Silverkeep.")

    user, assistant = at.chat_message
    assert (user.name, assistant.name) == ("user", "assistant")
    assert "A siege at Silverkeep." in markdown_values(user)
    assert REPAIRED in markdown_values(assistant)


def test_earlier_messages_stay_when_more_are_sent_or_settings_change(launch):
    at, fake = launch(result(REPAIRED_RESULT))

    send(at, "First idea.")
    send(at, "Second idea.")
    at.slider(key="max_repairs").set_value(1).run()

    assert [message.name for message in at.chat_message] == [
        "user", "assistant", "user", "assistant",
    ]
    assert len(fake.requests) == 2


def test_new_session_clears_the_conversation_and_returns_to_the_welcome(launch):
    at, _ = launch(result(REPAIRED_RESULT))
    send(at)

    at.button(key="new_session").click().run()

    assert not at.chat_message
    assert WELCOME_TAGLINE in page_text(at)
    assert "No scenes yet" in "\n".join(markdown_values(at.sidebar))


def test_the_sidebar_lists_the_scenes_of_the_conversation(launch):
    at, _ = launch(result(REPAIRED_RESULT))

    send(at, "A siege at Silverkeep.")
    send(at, "The queen's coronation.")

    sidebar_text = "\n".join(markdown_values(at.sidebar))
    assert "A siege at Silverkeep." in sidebar_text
    assert "The queen's coronation." in sidebar_text
    assert "No scenes yet" not in sidebar_text


# ---- the generated scene ----

def test_a_repaired_scene_shows_the_final_version_with_the_original_tucked_away(launch):
    at, _ = launch(result(REPAIRED_RESULT))
    send(at)

    original_shown = [m for m in at.markdown if m.value == ORIGINAL]
    assert len(original_shown) == 1
    assert ORIGINAL in markdown_values(expander(at, "View original generation"))
    assert expander(at, "View original generation").proto.expanded is False
    assert REPAIRED in page_text(at)


def test_a_scene_that_was_not_repaired_has_no_original_expander(launch):
    at, _ = launch(result([[SUPPORTED]], repairs=0, final=ORIGINAL))
    send(at)

    assert not has_expander(at, "View original generation")
    assert ORIGINAL in page_text(at)


# ---- the canon check ----

def test_the_canon_check_is_a_compact_status_line(launch):
    at, _ = launch(result(REPAIRED_RESULT))
    send(at)

    assert "Canon Check — 1 contradiction detected and repaired" in page_text(at)
    assert 'class="lk-canon lk-canon--verified"' in page_text(at)


def test_a_clean_scene_reads_verified_and_one_needing_review_is_flagged(launch):
    clean, _ = launch(result([[SUPPORTED]], repairs=0, final=ORIGINAL))
    send(clean)
    assert "Canon Check — Verified" in page_text(clean)

    flagged, _ = launch(result([[UNCERTAIN]], status="needs_review", repairs=0, final=ORIGINAL))
    send(flagged)
    assert "Canon Check — 1 uncertain claim needs review" in page_text(flagged)
    assert 'class="lk-canon lk-canon--review"' in page_text(flagged)


def test_a_repair_shows_the_progression_in_order(launch):
    at, _ = launch(result(REPAIRED_RESULT))
    send(at)

    text = page_text(at)
    order = [
        "Original generation",
        "Canon check found 1 contradiction",
        "Repair performed",
        "Rechecked",
        "Canon verified",
    ]
    positions = [text.index(label) for label in order]
    assert positions == sorted(positions)


def test_a_clean_scene_shows_no_progression(launch):
    at, _ = launch(result([[SUPPORTED]], repairs=0, final=ORIGINAL))
    send(at)

    assert '<ol class="lk-steps">' not in page_text(at)


def test_modes_without_verification_say_the_check_was_not_run(launch):
    at, _ = launch(result([], status="unverified", repairs=0, final=ORIGINAL))
    send(at)

    assert "Canon Check — Not run in this mode" in page_text(at)
    assert not has_expander(at, "View verification details")


# ---- verification details ----

def test_verification_details_start_collapsed_and_hold_a_card_per_claim(launch):
    at, _ = launch(
        result([[CONTRADICTION, SUPPORTED, NEW_ADDITION, UNCERTAIN]], status="needs_review")
    )
    send(at)

    details = expander(at, "View verification details")
    assert details.proto.expanded is False
    shown = "\n".join(markdown_values(details))
    for item in (CONTRADICTION, SUPPORTED, NEW_ADDITION, UNCERTAIN):
        assert item.claim in shown
        assert item.reason in shown
    for fact_id in ("fact-001", "fact-003", "fact-004"):
        assert fact_id in shown
    assert "none cited" in shown


def test_claims_show_their_classification_with_a_distinct_style_and_icon(launch):
    at, _ = launch(
        result([[CONTRADICTION, SUPPORTED, NEW_ADDITION, UNCERTAIN]], status="needs_review")
    )
    send(at)

    shown = "\n".join(markdown_values(expander(at, "View verification details")))
    expected = {
        "✅ SUPPORTED": "lk-chip--supported",
        "❌ CONTRADICTION": "lk-chip--contradiction",
        "➕ VALID NEW ADDITION": "lk-chip--valid-new-addition",
        "❓ UNCERTAIN": "lk-chip--uncertain",
    }
    for label, css_class in expected.items():
        assert label in shown
        assert css_class in shown


def test_claim_cards_say_whether_a_contradiction_was_repaired(launch):
    repaired, _ = launch(result(REPAIRED_RESULT))
    send(repaired)
    assert "Repaired in the final scene" in "\n".join(
        markdown_values(expander(repaired, "View verification details"))
    )

    stuck, _ = launch(
        result([[CONTRADICTION], [CONTRADICTION]], status="needs_review", repairs=1)
    )
    send(stuck)
    stuck_text = "\n".join(markdown_values(expander(stuck, "View verification details")))
    assert "Still unresolved" in stuck_text
    assert "Repaired in the final scene" not in stuck_text


def test_summary_counts_and_every_pass_live_inside_the_details(launch):
    at, _ = launch(result([[CONTRADICTION, UNCERTAIN], [SUPPORTED]]))
    send(at)

    shown = "\n".join(markdown_values(expander(at, "View verification details")))
    assert "Pass 1" in shown and "Pass 2" in shown
    assert "1 contradiction" in shown and "1 uncertain" in shown and "1 supported" in shown
    outside = [m.value for m in at.markdown if m.value not in shown]
    assert not any("1 supported" in value for value in outside)


# ---- artwork ----

def test_an_artwork_placeholder_appears_when_there_is_no_image(launch):
    at, _ = launch(result(REPAIRED_RESULT))
    send(at)

    assert "Concept artwork" in page_text(at)
    assert "once visual generation is connected" in page_text(at)
    assert not images(at)


def test_an_available_image_replaces_the_placeholder(launch, tmp_path):
    picture = tmp_path / "scene.png"
    picture.write_bytes(ONE_PIXEL_PNG)
    outcome = result(REPAIRED_RESULT)
    outcome.image_path = str(picture)
    at, _ = launch(outcome)

    send(at)

    assert not at.exception
    assert len(images(at)) == 1
    assert "once visual generation is connected" not in page_text(at)


# ---- errors and safety ----

def test_a_pipeline_error_is_shown_in_the_conversation_without_crashing(launch):
    at, _ = launch(RuntimeError("No verifier is configured."))

    send(at)

    assert not at.exception
    assert any("No verifier is configured." in error.value for error in at.error)
    assert [message.name for message in at.chat_message] == ["user", "assistant"]


def test_generated_text_is_never_rendered_as_html(launch):
    hostile = "<script>alert(1)</script>"
    claim = assessment(
        f"Claim {hostile}", ClaimClassification.CONTRADICTION, f"Reason {hostile}",
        ["fact-<img src=x onerror=alert(1)>"],
    )
    outcome = result([[claim], [SUPPORTED]], final=f"Scene {hostile}")
    at, _ = launch(outcome)

    send(at, f"Prompt {hostile}")

    assert not at.exception
    for element in at.markdown:
        if "<script>" in element.value or "<img src=x" in element.value:
            assert not element.allow_html, element.value[:80]
    assert any("&lt;img src=x" in m.value for m in at.markdown if m.allow_html)
    assert any(hostile in m.value for m in at.markdown)  # shown as plain text, not dropped


def test_the_stylesheet_is_injected_exactly_once(launch):
    at, _ = launch(result(REPAIRED_RESULT))
    send(at)

    styles = [m for m in at.markdown if m.value.lstrip().startswith("<style>")]
    assert len(styles) == 1 and styles[0].allow_html
    assert "--lk-crimson" in styles[0].value
