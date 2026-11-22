"""Exercise native assistant/tool/result loops, including zero-tool turns."""
import json
from unittest.mock import Mock

import pytest

from canon_memory.canon_store import CanonStore
from generation_engine.models import ChatRequest, ChatMessage, ConversationState
from generation_engine.ui_backend import handle_message
from shared.ai_client import AIClientError
from shared.schemas import CanonFact


def say(text):
    return {"role": "assistant", "content": text}


def call(name, **arguments):
    return {"role": "assistant", "content": None, "tool_calls": [{
        "id": name + "-call", "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }]}


class ScriptedAI:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.requests = []

    def chat_with_tools(self, messages, tools):
        self.requests.append(json.loads(json.dumps(messages)))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = CanonStore()
    store.add_fact("world_001", CanonFact(id="name", subject="vader", predicate="name", object="Darth Vader"))
    store.add_fact("world_001", CanonFact(id="hair", subject="vader", predicate="hair_color", object="black"))


def staged():
    ai = ScriptedAI(call("propose_canon", changes=[{
        "subject": "vader", "predicate": "former_name", "object": "Anakin Skywalker", "replaces_fact_id": "",
    }]), say("I can add that."))
    return handle_message(ChatRequest("Add that Darth Vader was once Anakin Skywalker"), client=ai)


@pytest.mark.parametrize("text", ["Hi", "What makes a good villain?", "Make that explanation shorter."])
def test_ordinary_conversation_needs_no_tools(text, monkeypatch):
    execute = Mock(side_effect=AssertionError("No tool should run"))
    monkeypatch.setattr("generation_engine.chat_tools.ChatTools.execute", execute)
    ai = ScriptedAI(say("A natural reply."))
    reply = handle_message(ChatRequest(text), client=ai)
    assert reply.message.content == "A natural reply."
    execute.assert_not_called()
    assert len(ai.requests) == 1
    assert ai.requests[0][-1] == {"role": "user", "content": text}


def test_multiple_tools_receive_actual_results_before_final_reply():
    ai = ScriptedAI(call("read_canon", query="Darth Vader"), call("propose_canon", changes=[{
        "subject": "vader", "predicate": "former_name", "object": "Anakin Skywalker", "replaces_fact_id": "",
    }]), say("Here is the proposed update."))
    result = handle_message(ChatRequest("What do we know about Vader? Add that he was Anakin Skywalker."), client=ai)
    assert result.pending_canon
    read_result = json.loads(ai.requests[1][-1]["content"])
    assert read_result["facts"] and read_result["status"] == "read"
    assert ai.requests[1][-1]["role"] == "tool"
    assert ai.requests[1][-1]["tool_call_id"] == "read_canon-call"
    assert json.loads(ai.requests[2][-1]["content"])["status"] == "pending_approval"
    assert "not saved yet" in result.message.content
    assert len(CanonStore().get_facts_by_world("world_001")) == 2


@pytest.mark.parametrize("text", ["yes please", "I approve this change", "jackass I approve this change"])
def test_approval_of_displayed_proposal(text):
    draft = staged()
    ai = ScriptedAI(call("approve_canon", proposal_token=draft.message.id, confirmation_quote=text), say("Saved."))
    result = handle_message(ChatRequest(text, history=[draft.message], pending_canon=draft.pending_canon), client=ai)
    assert result.pending_canon is None
    assert json.loads(ai.requests[1][-1]["content"])["status"] == "saved"
    assert any(f.object == "Anakin Skywalker" for f in CanonStore().get_facts_by_world("world_001"))


@pytest.mark.parametrize("text", ["No, don't approve", "yes but make it blue", "Hi", "should I approve?"])
def test_backend_rejects_unconfirmed_approval_even_if_model_calls_tool(text):
    draft = staged()
    ai = ScriptedAI(call("approve_canon", proposal_token=draft.message.id, confirmation_quote=text), say("Not saved."))
    result = handle_message(ChatRequest(text, history=[draft.message], pending_canon=draft.pending_canon), client=ai)
    assert result.pending_canon
    assert "error" in json.loads(ai.requests[1][-1]["content"])
    assert len(CanonStore().get_facts_by_world("world_001")) == 2


def test_cannot_approve_proposal_created_in_same_turn():
    ai = ScriptedAI(call("propose_canon", changes=[{
        "subject": "vader", "predicate": "former_name", "object": "Anakin", "replaces_fact_id": "",
    }]), call("approve_canon", proposal_token="invented", confirmation_quote="approve"), say("Please review."))
    result = handle_message(ChatRequest("Add Anakin and approve"), client=ai)
    assert result.pending_canon
    assert "error" in json.loads(ai.requests[2][-1]["content"])
    assert len(CanonStore().get_facts_by_world("world_001")) == 2


def test_world_scope_is_enforced_even_for_tool_arguments():
    ai = ScriptedAI(call("read_canon", query=""), say("The world is empty."))
    handle_message(ChatRequest("What's saved?", world_id="other"), client=ai)
    assert json.loads(ai.requests[1][-1]["content"])["facts"] == []
    ai = ScriptedAI(call("read_canon", query="", world_id="world_001"), say("Invalid request."))
    handle_message(ChatRequest("What's saved?", world_id="other"), client=ai)
    assert "error" in json.loads(ai.requests[1][-1]["content"])


def test_malformed_or_unknown_calls_return_errors_to_model():
    malformed = call("read_canon", query="")
    malformed["tool_calls"][0]["function"]["arguments"] = "not-json"
    ai = ScriptedAI(malformed, call("delete_everything"), say("I couldn't perform that action."))
    handle_message(ChatRequest("Hello"), client=ai)
    assert all("error" in json.loads(ai.requests[i][-1]["content"]) for i in (1, 2))


def test_save_survives_failure_of_following_model_response():
    draft = staged()
    ai = ScriptedAI(call("approve_canon", proposal_token=draft.message.id, confirmation_quote="yes"), AIClientError("secret"))
    reply = handle_message(ChatRequest("yes", history=[draft.message], pending_canon=draft.pending_canon), client=ai)
    assert reply.pending_canon is None
    assert "Saved" in reply.message.content
    assert "secret" not in reply.message.content


def test_repeated_calls_are_not_executed_twice_and_loop_is_bounded():
    repeated = call("read_canon", query="")
    ai = ScriptedAI(*([repeated] * 8))
    result = handle_message(ChatRequest("What is saved?"), client=ai)
    assert len(ai.requests) == 8
    assert "step limit" in result.message.content


def test_focus_and_recent_conversation_are_given_to_the_assistant():
    state = ConversationState("world_001", ["vader"])
    history = [ChatMessage("user", "Explain his motives", "world_001"),
               ChatMessage("assistant", "He wants control.", "world_001")]
    ai = ScriptedAI(say("He wants control."))
    handle_message(ChatRequest("Make it shorter", history=history, conversation=state), client=ai)
    assert ai.requests[0][-2]["content"] == "He wants control."
    assert "vader" in ai.requests[0][1]["content"]


def test_character_creator_is_called_and_draft_stays_unapproved():
    from generation_engine.character_creator import CharacterProfile
    ai = ScriptedAI(call("create_character", prompt="Create Mira, a thief"), say("Here is Mira."))
    ai.generate_structured = Mock(return_value=CharacterProfile(
        name="Mira", role="thief", appearance="black hair", background="a traveler",
        goal="find a key", flaw="impatient", attributes=[],
    ))
    result = handle_message(ChatRequest("Create Mira, a thief"), client=ai)
    assert result.pending_canon.name == "Mira"
    assert result.pending_canon.message_id == result.message.id
    assert "not saved yet" in result.message.content
    assert not any(f.object == "Mira" for f in CanonStore().get_facts_by_world("world_001"))


def test_scene_tool_verifies_repairs_and_preserves_verified_text():
    from continuity_checker.claim_extractor import ClaimProposals, ProposedClaim
    from continuity_checker.canon_verifier import Verdict
    ai = ScriptedAI(call("write_scene", instruction="Write about Darth Vader", target_message_id="", operation="generate_scene"),
                    say("An unverified paraphrase with green hair."))
    ai.generate_text = Mock(side_effect=["Darth Vader has red hair.", "Darth Vader has black hair."])
    ai.generate_structured = lambda instructions, text, schema: ClaimProposals(claims=[ProposedClaim(text=text, quote=text)])
    def compare(claim, fact):
        assert fact.subject == "Darth Vader"
        return Verdict.CONTRADICTION if fact.predicate == "hair_color" and "red" in claim.text else Verdict.ENTAILMENT
    reply = handle_message(ChatRequest("Write about Darth Vader"), client=ai, comparator_factory=lambda: compare)
    assert reply.message.pipeline.repair_attempts == 1
    assert reply.message.pipeline.status == "verified"
    assert reply.message.content == "Darth Vader has black hair."
    assert reply.active_scene_id == reply.message.id
    assert json.loads(ai.requests[-1][-1]["content"])["scene"] == reply.message.content


def test_image_tool_returns_asset_and_check_status(monkeypatch):
    from types import SimpleNamespace
    from shared.schemas import VisualAsset
    generate = Mock(return_value=VisualAsset(image_path="portrait.png", prompt="Vader"))
    monkeypatch.setattr("multimodal.visuals.generate_visual", generate)
    monkeypatch.setattr("multimodal.visuals.check_visual_facts", Mock(return_value=SimpleNamespace(checks=[
        SimpleNamespace(fact_id=f.id, status="match", explanation="Visible")
        for f in CanonStore().get_facts_by_world("world_001")
    ])))
    ai = ScriptedAI(call("generate_image", prompt="Draw Darth Vader", target_message_id=""), say("Here is the portrait."))
    result = handle_message(ChatRequest("Draw Darth Vader"), client=ai)
    assert result.message.asset.image_path == "portrait.png"
    assert result.message.visual_status == "no_mismatches_detected"
    assert json.loads(ai.requests[-1][-1]["content"])["image_created"]


def test_multiple_fact_tools_in_one_turn_keep_all_proposals():
    ai = ScriptedAI(call("propose_canon", changes=[{
        "subject": "vader", "predicate": "former_name", "object": "Anakin Skywalker", "replaces_fact_id": "",
    }]), call("propose_canon", changes=[{
        "subject": "vader", "predicate": "weapon", "object": "red lightsaber", "replaces_fact_id": "",
    }]), say("Here are both changes."))
    reply = handle_message(ChatRequest("Add that Vader was Anakin Skywalker and has a red lightsaber."), client=ai)
    assert {f.predicate for f in reply.pending_canon.facts} == {"former_name", "weapon"}
    assert "Anakin Skywalker" in reply.message.content and "red lightsaber" in reply.message.content
    assert reply.message.content.count("Shall I save") == 1
