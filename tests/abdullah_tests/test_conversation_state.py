from generation_engine.conversation import update_context
from generation_engine.models import ChatRequest, ChatMessage, ConversationState
from shared.schemas import CanonFact


FACTS = [CanonFact(id=name, subject=name, predicate="name", object=name.title()) for name in ("mira", "nora")]


def test_focus_survives_history_window():
    state = ConversationState("world_001", ["mira"])
    history = [ChatMessage("user", "Thanks", "world_001") for _ in range(25)]
    result = update_context(ChatRequest("What about her?", history=history, conversation=state), FACTS)
    assert result.focus_entity_ids == ["mira"]


def test_explicit_subject_switch_and_copy():
    state = ConversationState("world_001", ["mira"])
    result = update_context(ChatRequest("Tell me about Nora", conversation=state), FACTS)
    assert result.focus_entity_ids == ["nora"]
    assert state.focus_entity_ids == ["mira"]


def test_world_change_drops_context():
    state = ConversationState("other", ["mira"], "propose_fact", "private request")
    result = update_context(ChatRequest("Hello", conversation=state), FACTS)
    assert result.focus_entity_ids == []
    assert result.task_request == ""
