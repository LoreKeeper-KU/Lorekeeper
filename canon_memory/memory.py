# Written by Abdulaziz Albastaki in October 2026
import re

from canon_memory.canon_retriever import retrieve_by_entities
from canon_memory.canon_store import CanonStore
from shared.schemas import CanonFact

DEFAULT_WORLD_ID = "world_001"

def entity_names(facts: list[CanonFact]) -> dict[str, set[str]]:
    """Resolve approved display names and aliases, including legacy readable IDs."""
    names: dict[str, set[str]] = {}

    def register(name, entity_id):
        if name.strip():
            names.setdefault(name.strip().casefold(), set()).add(entity_id)

    for fact in facts:
        register(fact.subject, fact.subject)
        for entity_id in (fact.subject, fact.object):
            if entity_id.startswith(("char_", "loc_")):
                register(entity_id, entity_id)
                register(entity_id.split("_", 1)[1].replace("_", " "), entity_id)
        if fact.predicate in {"name", "alias", "former_name"}:
            register(fact.object, fact.subject)
    return names


def add_fact(fact: CanonFact) -> None:
    """Persist one accepted canon fact."""
    CanonStore().add_fact(DEFAULT_WORLD_ID, fact)


def retrieve_canon(query: str, *, world_id: str = DEFAULT_WORLD_ID) -> list[CanonFact]:
    """Resolve names against current approved facts in the requested world."""
    store = CanonStore()
    names = entity_names(store.get_facts_by_world(world_id))
    entity_ids = {
        entity_id
        for name, matches in names.items()
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", query.casefold())
        for entity_id in matches
    }

    if not entity_ids:
        return []

    return retrieve_by_entities(store, world_id, sorted(entity_ids))

def propose_update(fact: CanonFact) -> str:
    return CanonStore().propose_update(DEFAULT_WORLD_ID, fact)

def propose_revision(revised_fact: CanonFact) -> str:
    """Propose an edit to an existing fact in the default world."""
    return CanonStore().propose_revision(DEFAULT_WORLD_ID, revised_fact)


def approve_update(proposal_id: str) -> None:
    CanonStore().approve_update(proposal_id)
