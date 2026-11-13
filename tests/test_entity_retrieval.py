# Written by Abdulaziz Albastaki in November 2026
from pathlib import Path
from tempfile import TemporaryDirectory

from canon_memory.canon_store import CanonStore
from shared.schemas import CanonFact


with TemporaryDirectory() as temp_dir:
    store = CanonStore(
        db_path=Path(temp_dir) / "canon.db"
    )

    facts = [
        CanonFact(
            id="F001",
            subject="char_amina",
            predicate="hair_color",
            object="black"
        ),
        CanonFact(
            id="F002",
            subject="char_amina",
            predicate="magic_ability",
            object="none"
        ),
        CanonFact(
            id="F003",
            subject="char_amina",
            predicate="rules",
            object="Northern Kingdom"
        ),
        CanonFact(
            id="F004",
            subject="char_khalid",
            predicate="occupation",
            object="knight"
        )
    ]

    for fact in facts:
        store.add_fact("world_001", fact)

    results = store.get_facts_by_subject(
        "world_001",
        "char_amina"
    )

    for fact in results:
        print(f"{fact.subject} - {fact.predicate}: {fact.object}")

    assert len(results) == 3
    assert store.get_facts_by_subject(
        "world_002", "char_amina"
    ) == []

    print("Entity retrieval tests passed!")
