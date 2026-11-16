# Authored by Faris
import pytest

from continuity_checker.models import CanonFact
from continuity_checker.predicate_policy import is_exclusive


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
