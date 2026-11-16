proposal_id = store.propose_update("world_001", shield_fact)
assert store.get_fact(shield_fact.id) is None

store.approve_update(proposal_id)
assert store.get_fact(shield_fact.id) == shield_fact

store.approve_update(proposal_id)
assert store.get_facts_by_world("world_001") == [shield_fact]