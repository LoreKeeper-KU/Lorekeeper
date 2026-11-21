"""Exercise chat routing through the real pipelines with offline AI responses."""

import json
from unittest.mock import Mock

import pytest

from canon_memory.canon_store import CanonStore
from canon_memory.memory import retrieve_canon
from continuity_checker.canon_verifier import Verdict
from continuity_checker.claim_extractor import ClaimProposals, ProposedClaim
from generation_engine.character_creator import CharacterProfile
from generation_engine.chat_orchestrator import ChatRoute
from generation_engine.models import ChatMessage, ChatRequest
from generation_engine.ui_backend import handle_message, readable_canon
from shared.schemas import CanonFact


class OfflineAI:
    def __init__(self, intent, texts=(), target=""):
        self.route = ChatRoute(intent=intent, target_message_id=target)
        self.texts = iter(texts)
        self.calls = []

    def generate_structured(self, instructions, prompt, schema):
        self.calls.append((schema.__name__, instructions, prompt))
        if schema is ChatRoute:
            return self.route
        if schema is CharacterProfile:
            return CharacterProfile(
                name="Mira", role="Thief", appearance="Black hair",
                background="Grew up near the vault", goal="Steal the key",
                flaw="Impatient", attributes=[{"predicate": "hair_color", "object": "black"}],
            )
        if schema is ClaimProposals:
            return ClaimProposals(claims=[ProposedClaim(text=prompt, quote=prompt)])
        raise AssertionError(f"Unexpected model call: {schema}")

    def generate_text(self, instructions, prompt):
        self.calls.append(("text", instructions, prompt))
        return next(self.texts)


@pytest.fixture(autouse=True)
def temporary_world(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def seed(world="world_001"):
    store = CanonStore()
    facts = [
        CanonFact(id=world + "-name", subject="char_uuid", predicate="name", object="Mira"),
        CanonFact(id=world + "-hair", subject="char_uuid", predicate="hair_color", object="black"),
    ]
    for fact in facts:
        store.add_fact(world, fact)
    return facts


def supported(claim, fact):
    assert fact.subject == "Mira"  # UUID subjects were resolved before verification.
    return Verdict.ENTAILMENT


def test_character_creation_approval_and_scene_in_empty_world():
    model = OfflineAI("create_character")
    no_model_load = Mock(side_effect=AssertionError("Creation does not load NLI"))
    draft = handle_message(ChatRequest("Create Mira, a thief."), client=model,
                           comparator_factory=no_model_load)
    assert draft.message.kind == "draft"
    assert "approve" in draft.message.content
    assert retrieve_canon("Mira") == []
    assert draft.pending_canon is not None
    approved = handle_message(ChatRequest(
        "approve", history=[draft.message], pending_canon=draft.pending_canon,
    ), client=Mock(side_effect=AssertionError("Approval does not call AI")))
    assert approved.pending_canon is None
    facts = retrieve_canon("Write about Mira")
    assert len(facts) == len(draft.pending_canon.facts)
    assert {f.predicate: f.object for f in facts}["hair_color"] == "black"
    scene = handle_message(ChatRequest("Write a scene about Mira."),
                           client=OfflineAI("generate_scene", ["Mira has black hair."]),
                           comparator_factory=lambda: supported)
    assert scene.message.pipeline.status == "verified"
    assert scene.active_scene_id == scene.message.id
    assert scene.message.pipeline.reports[0].claims[0].evidence_fact_ids
    no_model_load.assert_not_called()


def test_scene_question_and_shortening_use_the_referenced_reply():
    seed()
    scene = handle_message(ChatRequest("Write a scene where Mira steals the key."),
                           client=OfflineAI("generate_scene", ["Mira reaches for the key with her left hand."]),
                           comparator_factory=lambda: supported)
    ai = OfflineAI("answer", ["The scene does not establish why; she might be keeping her right hand free."],
                   target=scene.message.id)
    answer = handle_message(ChatRequest(
        "Why did Mira use her left hand?", history=[scene.message], active_scene_id=scene.active_scene_id,
    ), client=ai, comparator_factory=Mock(side_effect=AssertionError("No NLI for explanations")))
    payload = json.loads(next(c[2] for c in ai.calls if c[0] == "text"))
    assert payload["referenced_scene"] == scene.message.content
    assert payload["accepted_canon"]
    assert "not established" in next(c[1] for c in ai.calls if c[0] == "text")
    assert answer.active_scene_id == scene.message.id

    shorter_ai = OfflineAI("revise", ["Her reason isn't established."], target=answer.message.id)
    shorter = handle_message(ChatRequest(
        "Make it shorter.", history=[scene.message, answer.message], active_scene_id=scene.message.id,
    ), client=shorter_ai)
    payload = json.loads(next(c[2] for c in shorter_ai.calls if c[0] == "text"))
    assert payload["target_reply"] == answer.message.content
    assert payload["referenced_scene"] == scene.message.content
    assert shorter.message.kind == "answer"
    assert shorter.message.pipeline is None
    assert shorter.active_scene_id == scene.message.id


def test_scene_revision_is_rechecked_and_repaired():
    seed()
    previous = ChatMessage("assistant", "Mira's black hair covers her eyes.", "world_001", kind="scene")
    ai = OfflineAI("revise", ["Mira has red hair.", "Mira has black hair."], target=previous.id)

    def compare(claim, fact):
        if fact.predicate == "hair_color":
            return Verdict.CONTRADICTION if "red" in claim.text else Verdict.ENTAILMENT
        return Verdict.NEUTRAL

    result = handle_message(ChatRequest(
        "Make it shorter.", history=[previous], active_scene_id=previous.id,
    ), client=ai, comparator_factory=lambda: compare)
    assert result.message.content == "Mira has black hair."
    assert result.message.pipeline.repair_attempts == 1
    assert result.message.pipeline.status == "verified"
    assert result.message.pipeline.initial_scene.text == "Mira has red hair."
    assert result.active_scene_id == result.message.id


def test_followup_reads_current_canon_not_previous_generated_facts():
    facts = seed()
    revised = facts[1].model_copy(update={"object": "silver"})
    store = CanonStore()
    store.approve_update(store.propose_revision("world_001", revised))
    old_scene = ChatMessage("assistant", "Mira has black hair.", "world_001", kind="scene")
    ai = OfflineAI("revise", ["Mira has silver hair."], target=old_scene.id)
    handle_message(ChatRequest("Make it shorter.", history=[old_scene], active_scene_id=old_scene.id),
                   client=ai, comparator_factory=lambda: supported)
    payload = json.loads(next(c[2] for c in ai.calls if c[0] == "text"))
    hair = [f for f in payload["accepted_canon"] if f["predicate"] == "hair_color"]
    assert hair[0]["object"] == "silver"


def test_world_isolation_filters_history_pending_and_retrieval():
    seed("other")
    old = ChatMessage("assistant", "Mira has black hair.", "other", kind="scene")
    ai = OfflineAI("generate_scene")
    result = handle_message(ChatRequest("Write about Mira.", history=[old], active_scene_id=old.id), client=ai)
    assert result.message.kind == "clarification"
    assert result.active_scene_id is None
    assert json.loads(ai.calls[0][2])["history"] == []
    assert retrieve_canon("Mira") == []
    assert retrieve_canon("Mira", world_id="other")


@pytest.mark.parametrize("target", ["", "invented"])
def test_revision_without_valid_context_asks_a_question(target):
    ai = OfflineAI("revise", target=target)
    result = handle_message(ChatRequest("Make it shorter."), client=ai)
    assert result.message.kind == "clarification"
    assert len(ai.calls) == 1


def test_pending_draft_is_never_used_as_approved_canon_and_can_be_discarded():
    draft = handle_message(ChatRequest("Create Mira."), client=OfflineAI("create_character"))
    result = handle_message(ChatRequest(
        "Write about her.", history=[draft.message], pending_canon=draft.pending_canon,
    ), client=OfflineAI("generate_scene", target=draft.message.id))
    assert result.message.kind == "clarification"
    assert result.pending_canon == draft.pending_canon
    discarded = handle_message(ChatRequest("discard", pending_canon=draft.pending_canon))
    assert discarded.pending_canon is None
    assert retrieve_canon("Mira") == []


def test_group_approval_is_atomic_world_scoped_and_idempotent():
    draft = handle_message(ChatRequest("Create Mira."), client=OfflineAI("create_character"))
    ids = draft.pending_canon.proposal_ids
    store = CanonStore()
    with pytest.raises(ValueError, match="another world"):
        store.approve_updates(ids, world_id_filter="other")
    with pytest.raises(KeyError):
        store.approve_updates([*ids, "missing"])
    assert retrieve_canon("Mira") == []
    store.approve_updates(ids, world_id_filter="world_001")
    store.approve_updates(ids, world_id_filter="world_001")
    assert len(retrieve_canon("Mira")) == len(ids)


def test_readable_canon_does_not_modify_stored_facts():
    facts = seed()
    readable = readable_canon(facts)
    assert readable[1].subject == "Mira"
    assert readable[1].id == facts[1].id
    assert facts[1].subject == "char_uuid"


def test_revising_pending_draft_replaces_only_the_pending_proposal():
    draft = handle_message(ChatRequest("Create Mira."), client=OfflineAI("create_character"))
    revised = handle_message(ChatRequest(
        "Change her background.", history=[draft.message], pending_canon=draft.pending_canon,
    ), client=OfflineAI("revise", target=draft.message.id))
    assert revised.message.kind == "draft"
    assert revised.pending_canon.message_id == revised.message.id
    assert revised.pending_canon.proposal_ids != draft.pending_canon.proposal_ids
    assert retrieve_canon("Mira") == []


def test_shortening_approved_profile_does_not_create_duplicate_canon():
    draft = handle_message(ChatRequest("Create Mira."), client=OfflineAI("create_character"))
    approved = handle_message(ChatRequest("approve", pending_canon=draft.pending_canon))
    before = retrieve_canon("Mira")
    shorter = handle_message(ChatRequest(
        "Shorten that profile.", history=[draft.message, approved.message],
    ), client=OfflineAI("revise", ["Mira is an impatient thief."], target=draft.message.id))
    assert shorter.pending_canon is None
    assert shorter.message.kind == "answer"
    assert retrieve_canon("Mira") == before
