# Written by Abdulaziz Albastaki in November 2026
from pathlib import Path
from tempfile import TemporaryDirectory

from canon_memory.canon_store import CanonStore
from shared.schemas import CanonFact


with TemporaryDirectory() as temp_dir:
    db_path = Path(temp_dir) / "canon.db"

    store = CanonStore(db_path=db_path)

    fact = CanonFact(
        id="F001",
        subject="char_amina",
        predicate="hair_color",
        object="black"
    )

    # Store the fact
    store.add_fact("world_001", fact)

    # Retrieve it
    retrieved = store.get_fact("F001")
    print("Retrieved:", retrieved)

    assert retrieved == fact

    # Reopen the database to verify persistence
    store = CanonStore(db_path=db_path)

    assert store.get_fact("F001") == fact

    # Another world must not see this fact in its world listing
    assert store.get_facts_by_world("world_002") == []

    print("All storage tests passed!")
