# Authored by Abdullah on 18/11/2026
# Adds sample canon for the local integration demo.
# Does not replace existing world facts.

import os
from pathlib import Path

from canon_memory.canon_store import CanonStore
from canon_memory.memory import DEFAULT_WORLD_ID
from shared.schemas import CanonFact


def main():
    # Use the database inside the main Lorekeeper repository.
    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)

    store = CanonStore()

    # Preserve any canon already stored for this world.
    existing = store.get_facts_by_world(DEFAULT_WORLD_ID)

    if existing:
        print("This world already contains facts. Nothing was added.")
        return

    facts = [
        CanonFact(
            id="demo-amina-rules",
            subject="char_amina",
            predicate="rules",
            object="loc_northern_kingdom",
        ),
        CanonFact(
            id="demo-amina-magic",
            subject="char_amina",
            predicate="magic_ability",
            object="none",
        ),
        CanonFact(
            id="demo-amina-hair",
            subject="char_amina",
            predicate="hair_color",
            object="black",
        ),
        CanonFact(
            id="demo-amina-eyes",
            subject="char_amina",
            predicate="eye_color",
            object="brown",
        ),
    ]

    # Fact IDs are unique across worlds. Check before inserting.
    for fact in facts:
        if store.get_fact(fact.id) is not None:
            raise ValueError(
                f"Fact ID already exists: {fact.id}. Nothing was added."
            )

    # Running this script accepts these sample facts for this demo.
    for fact in facts:
        store.add_fact(DEFAULT_WORLD_ID, fact)

    print(
        f"Added {len(facts)} sample facts to {DEFAULT_WORLD_ID}."
    )


if __name__ == "__main__":
    main()