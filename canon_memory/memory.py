# Written by Abdulaziz Albastaki in October 2026

"""LoreKeeper / CANON MEMORY (Owner: Abdulaziz)
=================================================
Purpose:
    Store accepted world facts and retrieve relevant facts for a story
    scene. You own *retrieval*, not claim verification or story repair.

EXAMPLE INPUT TO add_fact():
    CanonFact(
        id="fact-001",
        subject="Captain Arin",
        predicate="weapon",
        object="golden spear",
    )

EXAMPLE INPUT TO retrieve_canon():
    query = "Captain Arin meets Queen Lyra in Eldoria and recalls his father"

EXPECTED OUTPUT FROM retrieve_canon() (illustrative):
    [
        CanonFact(
            id="fact-001", subject="Captain Arin",
            predicate="weapon", object="golden spear"
        ),
        CanonFact(
            id="fact-002", subject="Queen Lyra",
            predicate="rules", object="Eldoria"
        ),
        CanonFact(
            id="fact-003", subject="Captain Arin's father",
            predicate="status", object="alive"
        ),
    ]

YOUR TODOs:
    1. Choose how to persist canon (e.g. SQLite for facts).
    2. Implement add_fact() and retrieve_canon().
    3. Add relationship-aware retrieval (e.g. NetworkX/graph queries).
    4. Optionally add semantic retrieval (e.g. ChromaDB).
    5. Write tests that verify relevant facts are returned.

INTEGRATION CONTRACT:
    Faris and Abdullah consume list[CanonFact] from retrieve_canon().
    Saif can use the same facts to keep visuals consistent.
    Do not change the public function signatures without team agreement.
"""

from shared.schemas import CanonFact


def add_fact(fact: CanonFact) -> None:
    """Persist one new accepted canon fact; raise on invalid/duplicate data."""
    # TODO (Abdulaziz): Save to your selected storage backend.
    raise NotImplementedError("Abdulaziz: implement add_fact")


def retrieve_canon(query: str) -> list[CanonFact]:
    """Retrieve the canon facts most relevant to a scene or question."""
    # TODO (Abdulaziz): Return CanonFact objects, not raw dictionaries.
    raise NotImplementedError("Abdulaziz: implement retrieve_canon")
