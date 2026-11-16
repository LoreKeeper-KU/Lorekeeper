# Written by Abdulaziz Albastaki in Novemeber 2026
from pathlib import Path
from tempfile import TemporaryDirectory

from canon_memory.canon_store import CanonStore
from canon_memory.knowledge_graph import KnowledgeGraph
from shared.schemas import CanonFact


with TemporaryDirectory() as temp_dir:
    store = CanonStore(Path(temp_dir) / "canon.db")

    facts = [
        CanonFact(
            id="F001",
            subject="char_amina",
            predicate="rules",
            object="loc_northern_kingdom"
        ),
        CanonFact(
            id="F002",
            subject="char_khalid",
            predicate="brother_of",
            object="char_amina"
        ),
        CanonFact(
            id="F003",
            subject="char_khalid",
            predicate="lives_in",
            object="loc_frosthaven"
        )
    ]

    for fact in facts:
        store.add_fact("world_001", fact)

    # Construct a graph using this world's approved facts
    graph = KnowledgeGraph(
        store.get_facts_by_world("world_001")
    )

    results = graph.get_related_facts("char_amina")

    for fact in results:
        print(
            f"{fact.subject} -> "
            f"{fact.predicate} -> "
            f"{fact.object}"
        )

    assert {fact.id for fact in results} == {
        "F001", "F002"
    }

    print("Knowledge graph tests passed!")
