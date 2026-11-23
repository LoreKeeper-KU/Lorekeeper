from canon_memory.canon_store import CanonStore
from shared.schemas import CanonFact


def test_approval_persists_and_is_idempotent(tmp_path):
    store = CanonStore(tmp_path / "canon.db")
    fact = CanonFact(id="shield", subject="char_mira", predicate="owns", object="silver shield")
    proposal = store.propose_update("world_001", fact)
    assert store.get_fact(fact.id) is None
    store.approve_update(proposal)
    reopened = CanonStore(tmp_path / "canon.db")
    assert reopened.get_fact(fact.id) == fact
    reopened.approve_update(proposal)
    assert reopened.get_facts_by_world("world_001") == [fact]
