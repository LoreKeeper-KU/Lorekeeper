"""Chat UI contract: one input, one backend entry point, no UI intent routing."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from generation_engine.models import ChatMessage, ChatReply, PendingCanon, ConversationState
from ui_builders import result, CONTRADICTION, SUPPORTED

APP = Path(__file__).resolve().parents[2] / "app.py"


@pytest.fixture
def launch(monkeypatch):
    def start(kind="answer", pipeline=None):
        def respond(request, **services):
            turn = ChatMessage(
                role="assistant", content="A reply from the backend.",
                world_id=request.world_id, kind=kind, pipeline=pipeline,
            )
            return ChatReply(turn, active_scene_id=turn.id if kind == "scene" else request.active_scene_id)
        backend = Mock(side_effect=respond)
        monkeypatch.setattr("generation_engine.ui_backend.handle_message", backend)
        return AppTest.from_file(str(APP), default_timeout=30).run(), backend
    return start


def send(app, prompt):
    return app.chat_input[0].set_value(prompt).run()


def test_single_input_without_workflow_controls(launch):
    app, backend = launch()
    assert not app.exception
    assert len(app.chat_input) == 1
    assert not app.radio
    assert not app.selectbox
    assert not app.text_input
    assert not app.get("form")
    assert not app.chat_message
    assert "Build worlds that remember." in " ".join(m.value for m in app.markdown)
    backend.assert_not_called()


def test_forwards_free_text_and_context_without_an_action(launch):
    app, backend = launch(kind="scene")
    send(app, "Write a scene where Mira steals the key.")
    assert not app.exception
    first = backend.call_args.args[0]
    assert first.message == "Write a scene where Mira steals the key."
    assert first.history == []
    assert first.world_id == "world_001"
    assert not hasattr(first, "action")
    assert not hasattr(first, "mode")
    send(app, "Why did she do that?")
    followup = backend.call_args.args[0]
    assert [m.role for m in followup.history] == ["user", "assistant"]
    assert followup.history[-1].content == "A reply from the backend."
    assert followup.active_scene_id == followup.history[-1].id
    assert len(app.chat_message) == 4
    assert not app.exception


def test_rerender_does_not_regenerate_and_blank_input_is_ignored(launch):
    app, backend = launch()
    send(app, "   ")
    backend.assert_not_called()
    send(app, "Hello")
    app.run()
    backend.assert_called_once()
    assert len(app.chat_message) == 2


def test_new_chat_clears_context_but_keeps_world(launch):
    app, backend = launch(kind="scene")
    app.session_state["world_id"] = "my_world"
    send(app, "Write about Mira")
    app.session_state["pending_canon"] = PendingCanon("my_world", "Mira", [], [])
    app.session_state["conversation"] = ConversationState("my_world", ["mira"])
    app.button(key="new_session").click().run()
    assert app.session_state["messages"] == []
    assert app.session_state["active_scene_id"] is None
    assert app.session_state["pending_canon"] is None
    assert app.session_state["conversation"] is None
    assert app.session_state["world_id"] == "my_world"
    assert not app.chat_message


def test_ui_forwards_backend_conversation_state(launch):
    app, backend = launch()
    state = ConversationState("world_001", ["mira"], "propose_fact", "Change her hair color", "Which color?")
    backend.side_effect = lambda request, **kwargs: ChatReply(
        ChatMessage("assistant", "Which color?", request.world_id), conversation=state
    )
    send(app, "Change Mira's hair color")
    assert app.session_state["conversation"] == state
    send(app, "silver")
    assert backend.call_args.args[0].conversation == state


def test_corrections_are_collapsed_under_reply(launch):
    pipeline = result([[CONTRADICTION], [SUPPORTED]])
    app, _ = launch(kind="scene", pipeline=pipeline)
    send(app, "Write a scene")
    assert not app.exception
    checks = [e for e in app.expander if e.label == "Canon checks"]
    assert len(checks) == 1
    assert checks[0].proto.expanded is False
    assert "Before correction" in " ".join(m.value for m in checks[0].markdown)
    assert any(m.value == "A reply from the backend." for m in app.markdown)


def test_answers_do_not_claim_verification(launch):
    app, _ = launch()
    send(app, "Why did Mira use her left hand?")
    assert not app.expander
    assert not app.exception


def test_errors_keep_conversation_context_and_hide_raw_provider_output(launch):
    app, backend = launch(kind="scene")
    send(app, "Write about Mira")
    scene_id = app.session_state["active_scene_id"]
    backend.side_effect = RuntimeError("secret-provider-response")
    send(app, "Make it shorter")
    assert not app.exception
    assert len(app.error) == 1
    assert "secret-provider-response" not in app.error[0].value
    assert app.session_state["active_scene_id"] == scene_id
    assert len(app.session_state["messages"]) == 4


def test_draft_and_approval_use_the_same_input(monkeypatch):
    pending = PendingCanon("world_001", "Mira", [], ["proposal"])
    requests = []
    def backend(request, **kwargs):
        requests.append(request)
        if len(requests) == 1:
            return ChatReply(ChatMessage("assistant", "Mira draft. Reply approve to save.",
                                         request.world_id, kind="draft"), pending_canon=pending)
        assert request.pending_canon == pending
        return ChatReply(ChatMessage("assistant", "Saved Mira.", request.world_id, kind="note"))
    monkeypatch.setattr("generation_engine.ui_backend.handle_message", backend)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    send(app, "Create Mira")
    send(app, "approve")
    assert not app.exception
    assert [r.message for r in requests] == ["Create Mira", "approve"]
    assert app.session_state["pending_canon"] is None
    assert len(app.chat_input) == 1
