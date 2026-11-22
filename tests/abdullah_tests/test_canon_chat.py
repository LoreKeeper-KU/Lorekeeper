"""Canon validation beneath the conversational tool interface."""
import pytest
from canon_memory.canon_store import CanonStore
from generation_engine.canon_editor import FactChange, FactChanges, prepare_fact_changes
from shared.schemas import CanonFact


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = CanonStore()
    store.add_fact("world_001", CanonFact(id="name", subject="mira", predicate="name", object="Mira"))
    store.add_fact("world_001", CanonFact(id="hair", subject="mira", predicate="hair_color", object="black"))


def test_missing_value_is_not_invented():
    pending, text = prepare_fact_changes({"message": "Change her hair color"}, "world_001", FactChanges(changes=[
        FactChange(subject="mira", predicate="hair_color", object="changed")
    ]))
    assert pending is None
    assert "hair color" in text


def test_short_followup_and_revision_history():
    pending, _ = prepare_fact_changes({"message": "silver", "conversation_state": {"original_request": "Change Mira's hair color"}},
                                     "world_001", FactChanges(changes=[FactChange(subject="mira", predicate="hair_color", object="silver")]))
    store = CanonStore()
    store.approve_updates(pending.proposal_ids, world_id_filter="world_001")
    assert store.get_fact("hair").object == "silver"
    assert store.get_fact_history("world_001", "hair")[0][1].object == "black"


def test_unknown_subject_is_rejected():
    pending, _ = prepare_fact_changes({"message": "Add a fact"}, "world_001", FactChanges(changes=[
        FactChange(subject="other", predicate="name", object="Nora")
    ]))
    assert pending is None


def test_atomic_approval_rolls_back_on_missing_proposal():
    pending, _ = prepare_fact_changes({"message": "Make Mira's hair silver"}, "world_001", FactChanges(changes=[
        FactChange(subject="mira", predicate="hair_color", object="silver")
    ]))
    with pytest.raises(KeyError):
        CanonStore().approve_updates([*pending.proposal_ids, "missing"])
    assert CanonStore().get_fact("hair").object == "black"
