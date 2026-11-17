# Written by Abdulaziz Albastaki in Novemeber 2026
from canon_memory.memory import add_fact, retrieve_canon
from shared.schemas import CanonFact


def test_retrieve_canon_finds_incoming_relationship(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    fact = CanonFact(
        id="F001",
        subject="char_khalid",
        predicate="brother_of",
        object="char_amina",
    )
    add_fact(fact)

    assert retrieve_canon("What do we know about Amina?") == [fact]