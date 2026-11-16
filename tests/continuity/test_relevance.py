# Authored by Faris
from continuity_checker.models import CanonFact, Claim, SourceSpan
from continuity_checker.relevance import select_relevant_facts

SPEAR = CanonFact(id="fact-001", subject="Captain Arin", predicate="weapon", object="golden spear")
LYRA = CanonFact(id="fact-002", subject="Queen Lyra", predicate="rules", object="Eldoria")
FATHER = CanonFact(
    id="fact-003", subject="Captain Arin's father", predicate="status", object="alive"
)


def claim(text):
    return Claim(claim_id="C001", text=text, source_span=SourceSpan(start=0, end=10))


def ids(text, facts):
    return [f.id for f in select_relevant_facts(claim(text), facts)]


def test_a_fact_whose_subject_is_named_in_the_claim_is_relevant():
    assert ids("Arin drew a silver sword.", [SPEAR]) == ["fact-001"]


def test_an_unrelated_fact_is_dropped():
    assert ids("Arin drew a silver sword.", [SPEAR, LYRA]) == ["fact-001"]


def test_a_fact_whose_object_is_named_in_the_claim_is_relevant():
    assert ids("Arin entered the royal palace in Eldoria.", [LYRA]) == ["fact-002"]
    assert ids("Arin dropped the golden spear.", [SPEAR]) == ["fact-001"]


def test_the_predicate_alone_never_makes_a_fact_relevant():
    other_ruler = CanonFact(id="f9", subject="King Orin", predicate="rules", object="Valdoria")
    assert ids("Queen Lyra rules Eldoria.", [other_ruler]) == []


def test_function_words_alone_never_make_a_fact_relevant():
    order = CanonFact(id="f8", subject="The Order", predicate="is", object="of the West")
    assert ids("The queen greeted him in the hall.", [order]) == []


def test_titles_still_match_so_the_queen_links_to_queen_lyra():
    assert ids("The queen greeted him warmly.", [LYRA]) == ["fact-002"]


def test_matching_ignores_case_possessives_and_punctuation():
    assert ids("ARIN'S father died in the Great War!", [FATHER]) == ["fact-003"]


def test_underscored_ids_are_split_into_words():
    amina = CanonFact(id="F002", subject="char_amina", predicate="magic_ability", object="none")
    assert ids("Amina can summon magical firestorms.", [amina]) == ["F002"]


def test_input_order_is_kept_and_no_facts_gives_an_empty_list():
    assert ids("Arin met Queen Lyra in Eldoria.", [LYRA, SPEAR, FATHER]) == [
        "fact-002",
        "fact-001",
        "fact-003",
    ]
    assert ids("Arin drew a sword.", []) == []
