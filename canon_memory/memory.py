# Written by Abdulaziz Albastaki in October 2026
import re

from canon_memory.canon_retriever import retrieve_by_entities
from canon_memory.canon_store import CanonStore
from shared.schemas import CanonFact

DEFAULT_WORLD_ID = "world_001"

ENTITY_ALIASES = {
    "amina": "char_amina",
    "khalid": "char_khalid",
    "northern kingdom": "loc_northern_kingdom",
}


def add_fact(fact: CanonFact) -> None:
    """Persist one accepted canon fact."""
    CanonStore().add_fact(DEFAULT_WORLD_ID, fact)


def retrieve_canon(query: str) -> list[CanonFact]:
    """Retrieve canon facts involving known entities named in the query."""
    entity_ids = [
        entity_id
        for name, entity_id in ENTITY_ALIASES.items()
        if re.search(rf"\b{re.escape(name)}\b", query, flags=re.IGNORECASE)
    ]

    if not entity_ids:
        return []

    return retrieve_by_entities(CanonStore(), DEFAULT_WORLD_ID, entity_ids)

def propose_update(fact: CanonFact) -> str:
    return CanonStore().propose_update(DEFAULT_WORLD_ID, fact)

def propose_revision(revised_fact: CanonFact) -> str:
    """Propose an edit to an existing fact in the default world."""
    return CanonStore().propose_revision(DEFAULT_WORLD_ID, revised_fact)


def approve_update(proposal_id: str) -> None:
    CanonStore().approve_update(proposal_id)
