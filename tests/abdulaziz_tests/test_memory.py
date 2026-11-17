# Written by Abdulaziz Albastaki in Novemeber 2026
from canon_memory.canon_store import CanonStore
from canon_memory.memory import (
    DEFAULT_WORLD_ID,
    add_fact,
    approve_update,
    propose_revision,
    retrieve_canon,
)
from shared.schemas import CanonFact


def test_approved_revision_replaces_current_fact_and_preserves_history(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    silver = CanonFact(
        id="F005",
        subject="char_amina",
        predicate="owns",
        object="silver shield",
    )
    gold = silver.model_copy(update={"object": "gold shield"})
    query = "What does Amina own?"

    add_fact(silver)
    proposal_id = propose_revision(gold)
    assert retrieve_canon(query) == [silver]

    approve_update(proposal_id)

    assert retrieve_canon(query) == [gold]
    assert CanonStore().get_fact_history(DEFAULT_WORLD_ID, "F005") == [(1, silver)]