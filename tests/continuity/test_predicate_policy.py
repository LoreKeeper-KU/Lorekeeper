# Authored by Faris
import pytest

from continuity_checker.models import CanonFact
from continuity_checker.predicate_policy import (
    is_exclusive,
    mentions_topic,
    refers_to_attribute,
    supports_topic,
)


def fact(predicate, obj="x"):
    return CanonFact(id="f1", subject="Arin", predicate=predicate, object=obj)


@pytest.mark.parametrize("predicate", ["status", "eye_color", "hair_color", "species", "birthplace"])
def test_single_valued_predicates_are_exclusive(predicate):
    assert is_exclusive(fact(predicate))


@pytest.mark.parametrize("predicate", ["father", "mother", "house", "allegiance"])
def test_single_valued_relationships_are_exclusive(predicate):
    # A person has one father, one mother, one house and one sworn allegiance (see the
    # benchmark's LABELLING_POLICY.md), so a conflicting value is a contradiction.
    assert is_exclusive(fact(predicate, "Someone"))


@pytest.mark.parametrize(
    "predicate", ["weapon", "tool", "pet", "vehicle", "rules", "magic_ability", "ally_of"]
)
def test_other_predicates_are_not_exclusive_by_default(predicate):
    assert not is_exclusive(fact(predicate))


@pytest.mark.parametrize("predicate", ["Eye Color", "eye-color", " EYE_COLOR ", "Father", " MOTHER "])
def test_predicate_spelling_is_normalised(predicate):
    assert is_exclusive(fact(predicate))


@pytest.mark.parametrize("obj", ["none", "None", "nobody", "No one", "nothing", "never"])
def test_an_explicit_none_object_is_exclusive_whatever_the_predicate(obj):
    assert is_exclusive(fact("weapon", obj))
    assert is_exclusive(fact("magic_ability", obj))


def test_a_value_that_merely_contains_none_is_not_treated_as_a_negation():
    assert not is_exclusive(fact("weapon", "nonetheless a spear"))


def test_the_exclusive_predicates_can_be_replaced():
    assert is_exclusive(fact("weapon"), exclusive_predicates=frozenset({"weapon"}))
    assert not is_exclusive(fact("status"), exclusive_predicates=frozenset())


# ---- refers_to_attribute: does the claim talk about the attribute the fact states? ----

@pytest.mark.parametrize(
    "predicate, claim",
    [
        ("eye_color", "Kael has blue eyes."),
        ("eye_color", "Her blue-eyed stare held him."),
        ("hair_color", "Kael has red hair."),
        ("hair_color", "He was blond."),
        ("magic_ability", "Kael cast a fire spell."),
        ("magic_ability", "Elara summoned a storm cloud over the courtyard."),
        ("magic_ability", "Amina can summon magical firestorms."),
    ],
)
def test_a_claim_refers_to_an_attribute_when_it_uses_one_of_its_cue_words(predicate, claim):
    assert refers_to_attribute(claim, fact(predicate))


@pytest.mark.parametrize(
    "predicate, claim",
    [
        ("eye_color", "Kael had a pack mule."),
        ("hair_color", "Kael had a mule."),
        ("magic_ability", "Mira stopped at once."),
        ("magic_ability", "Kael led the mule forward."),
        ("eye_color", "A bird startled from a nearby pine."),
    ],
)
def test_a_claim_that_never_mentions_the_attribute_does_not_refer_to_it(predicate, claim):
    assert not refers_to_attribute(claim, fact(predicate))


def test_cue_words_must_match_whole_words():
    # "cast" sits inside "castle" and "hair" inside "chairs"; neither is a mention.
    assert not refers_to_attribute("The castle stood on the hill.", fact("magic_ability"))
    assert not refers_to_attribute("He pulled up two chairs.", fact("hair_color"))


@pytest.mark.parametrize("predicate", ["Eye Color", "eye-color", " EYE_COLOR "])
def test_matching_ignores_case_punctuation_and_predicate_spelling(predicate):
    assert refers_to_attribute("KAEL HAS BLUE EYES!", fact(predicate))
    assert not refers_to_attribute("KAEL HAD A MULE!", fact(predicate))


@pytest.mark.parametrize(
    "predicate, obj",
    [
        ("status", "alive"),
        ("species", "android"),
        ("birthplace", "Kharsa"),
        ("father", "Tomas Voss"),
        ("mother", "Nadira"),
        ("house", "House Lumen"),
        ("allegiance", "Port Calder Police"),
        ("mechanical_skill", "none"),
        ("weapon", "golden spear"),
    ],
)
def test_other_predicates_are_never_filtered(predicate, obj):
    """Their values are open-ended or implied ("funeral procession" for status), so no cue list
    can tell whether a claim is about them; a conflict with them is left as it is."""
    assert refers_to_attribute("Kael had a pack mule.", fact(predicate, obj))


def test_the_cue_words_can_be_replaced():
    cues = {"weapon": frozenset({"sword", "spear"})}
    assert refers_to_attribute("He drew a sword.", fact("weapon"), attribute_cues=cues)
    assert not refers_to_attribute("He had a mule.", fact("weapon"), attribute_cues=cues)
    assert refers_to_attribute("He had a mule.", fact("eye_color"), attribute_cues=cues)


# ---- mentions_topic: is the claim about a non-exclusive fact's subject matter? ----

def kael_fact(predicate, obj):
    return CanonFact(id="f1", subject="Kael", predicate=predicate, object=obj)


@pytest.mark.parametrize(
    "predicate, obj, claim",
    [
        ("occupation", "cartographer", "Kael worked as a cartographer in the north."),  # the value
        ("occupation", "cartographer", "Kael's occupation changed that winter."),  # the slot name
        ("goal", "To finish a complete map of the northern passes.", "Kael drew a map of the northern passes."),
        ("goal", "To finish a complete map of the northern passes.", "Kael mapped the passes."),  # plural
        ("magic_ability", "minor mystical protection", "Kael cast a spell on the gate."),  # cue words
        ("role", "Wandering cartographer", "Kael was a wanderer, never a cartographer."),
    ],
)
def test_a_claim_that_shares_a_topic_word_with_the_fact_is_about_it(predicate, obj, claim):
    assert mentions_topic(claim, kael_fact(predicate, obj))


@pytest.mark.parametrize(
    "predicate, obj, claim",
    [
        ("occupation", "cartographer", "Kael brushed moss from the road."),
        ("role", "Wandering cartographer", "Kael led the mule forward."),
        ("flaw", "He is stubborn about his own measurements.", "Kael had a pack mule."),
        ("magic_ability", "minor mystical protection", "Kael said 'Enough.'"),
        ("goal", "To forge a lasting kingdom built on justice.", "Kael said 'Enough.'"),
    ],
)
def test_a_claim_that_shares_nothing_with_the_fact_is_not_about_it(predicate, obj, claim):
    assert not mentions_topic(claim, kael_fact(predicate, obj))


def test_the_subjects_own_name_is_not_a_topic():
    """Every claim about Kael names Kael, so a fact that merely repeats the name links nothing."""
    assert not mentions_topic("Kael stopped at once.", kael_fact("name", "Kael"))
    king = CanonFact(id="f2", subject="king arthur", predicate="name", object="king arthur")
    assert not mentions_topic("King Arthur said 'Enough.'", king)


def test_filler_words_alone_are_not_a_topic():
    fact_ = kael_fact("flaw", "He will not turn back once a route is chosen.")
    assert not mentions_topic("Kael would not say more once they left.", fact_)


@pytest.mark.parametrize("predicate", ["weapon", "tool", "pet", "vehicle"])
def test_slot_predicates_are_never_filtered(predicate):
    """A different weapon, tool, pet or vehicle is the tension this policy reports, however the
    claim is worded ("drew a steel dagger" never says "weapon")."""
    assert mentions_topic("Kael brushed moss from the road.", kael_fact(predicate, "a curved katana"))


# ---- supports_topic: may this fact count as support for the claim? ----

@pytest.mark.parametrize(
    "predicate, obj, claim",
    [
        ("build", "lean", "Nora is lean."),
        ("build", "lean", "Nora has a lean build."),
        ("occupation", "scout", "Nora is a scout."),
        ("goal", "To find her missing brother.", "Nora is looking for her brother."),
        ("magic_ability", "minor mystical protection", "Nora can cast protective spells."),
    ],
)
def test_a_fact_the_claim_restates_can_support_it(predicate, obj, claim):
    fact_ = CanonFact(id="f1", subject="Nora", predicate=predicate, object=obj)
    assert supports_topic(claim, fact_)


@pytest.mark.parametrize(
    "predicate, obj, claim",
    [
        ("build", "lean", "Nora stepped closer."),
        ("appearance", "A lean, quick-footed woman with cropped dark hair.", "Nora ran."),
        ("flaw", "She trusts her instincts over any plan.", "Nora followed the path."),
        ("background", "Nora grew up guiding caravans through the salt flats.", "Nora walked to the door."),
        ("role", "Scout", "Nora opened the gate."),
    ],
)
def test_a_fact_the_claim_is_not_about_cannot_support_it(predicate, obj, claim):
    fact_ = CanonFact(id="f1", subject="Nora", predicate=predicate, object=obj)
    assert not supports_topic(claim, fact_)


@pytest.mark.parametrize("predicate", ["weapon", "tool", "pet", "vehicle"])
def test_slot_facts_are_not_exempt_from_the_support_check(predicate):
    """Slots are exempt when reporting *tension* (a different weapon), never when supporting."""
    fact_ = CanonFact(id="f1", subject="Nora", predicate=predicate, object="a curved katana")
    assert mentions_topic("Nora stepped closer.", fact_)
    assert not supports_topic("Nora stepped closer.", fact_)
    assert supports_topic("Nora drew her curved katana.", fact_)


def test_the_support_cue_words_can_be_replaced():
    cues = {"build": frozenset({"closer"})}
    fact_ = CanonFact(id="f1", subject="Nora", predicate="build", object="lean")
    assert supports_topic("Nora stepped closer.", fact_, attribute_cues=cues)


def test_the_topic_words_and_slot_predicates_can_be_replaced():
    assert mentions_topic("Kael had a mule.", kael_fact("occupation", "x"), slot_predicates=frozenset({"occupation"}))
    cues = {"occupation": frozenset({"mule"})}
    assert mentions_topic("Kael had a mule.", kael_fact("occupation", "x"), attribute_cues=cues)
