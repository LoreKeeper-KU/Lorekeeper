# Authored by Faris
"""is_scene_detail: which claims are anonymous scenery rather than statements about someone."""

import pytest

from continuity_checker.scene_detail import is_scene_detail


@pytest.mark.parametrize(
    "claim",
    [
        "A bird startled from a nearby pine.",
        "The road was half-swallowed by earth and roots.",
        "There was a clear trail home to the south.",
        "The cry came again, weaker this time.",
        "The merchant sold bread.",
        "It was quiet in the hollow.",
        "Somewhere a dog barked.",
        "Wind moved through the pines.",
        "The old man whispered \"Enough.\"",  # a capital after an opening quote starts a sentence
    ],
)
def test_anonymous_scenery_is_a_scene_detail(claim):
    assert is_scene_detail(claim)


@pytest.mark.parametrize(
    "claim",
    [
        "Moss blurred the bridge's edges.",
        "Cracks split the stones of the bridge.",
        "Shadows pooled under the arch.",
        "Ravens circled overhead.",
        "Stones lay scattered on the path.",
    ],
)
def test_scenery_that_opens_with_an_ordinary_noun_is_a_scene_detail(claim):
    assert is_scene_detail(claim)


@pytest.mark.parametrize(
    "claim",
    [
        "Someone had tended the lock.",
        "Somebody had swept the steps.",
        "Nobody answered the call.",
        "Something rustled in the reeds.",
        "Everything was still.",
        "No footsteps sounded in the street.",
        "Several crows sat on the wall.",
    ],
)
def test_scenery_that_opens_with_an_indefinite_pronoun_or_quantifier_is_a_scene_detail(claim):
    """These words are never names, and live scenes use them for harmless background detail."""
    assert is_scene_detail(claim)


@pytest.mark.parametrize(
    "claim",
    [
        "Madame Orlova runs the fish market.",
        "Merchant Hanan sells spices in the northern bazaar.",
        "The road to Silverkeep was empty.",  # a named place
        "A bird startled from a pine near Ashford.",
        "Zayd defended the city.",  # a sentence-initial name is not scenery
        "Silas defended the city.",  # not even one that ends in "s" like a plural noun
        "Nora stepped closer.",
        "Kael had a mule.",
        "He nodded.",
        "She stopped at once.",
        "",
    ],
)
def test_claims_that_name_someone_or_do_not_open_like_scenery_are_not(claim):
    assert not is_scene_detail(claim)


def test_the_pronoun_I_is_not_a_name():
    assert is_scene_detail("There I heard the cry again.")


def test_the_opening_words_can_be_replaced():
    assert is_scene_detail("Zayd defended the city.", openers=frozenset({"zayd"}))
    assert not is_scene_detail("The cry came again.", openers=frozenset({"zayd"}))
