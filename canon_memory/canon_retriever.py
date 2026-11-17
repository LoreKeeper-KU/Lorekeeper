from canon_memory.canon_store import CanonStore
from shared.schemas import CanonFact
from canon_memory.knowledge_graph import KnowledgeGraph

def retrieve_by_entities(
    store: CanonStore,
    world_id: str,
    entities: list[str],
) -> list[CanonFact]:
    # 1. Build a KnowledgeGraph from store.get_facts_by_world(world_id).
    world_facts = store.get_facts_by_world(world_id)
    graph = KnowledgeGraph(world_facts)
    # 2. Call graph.get_related_facts(entity) for each entity ID.
    facts_by_id: dict[str, CanonFact] = {}
    for entity_id in entities:
      for fact in graph.get_related_facts(entity_id):
         facts_by_id[fact.id] = fact
    return [facts_by_id[fact_id] for fact_id in sorted(facts_by_id)]