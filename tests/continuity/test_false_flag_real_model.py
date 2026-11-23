# Authored by Faris
"""The false-flag regression cases against the real NLI model. Run with: python -m pytest -m model

Same facts and expectations as test_false_flag_regressions.py, but the comparison is made by the
real DeBERTa model instead of a scripted one. Slow (loads the model), so kept out of the normal
suite. No API key is needed: only the addition judge is faked.

Written before the fix: the "false flag" tests are expected to FAIL until the continuity logic is
corrected, and the guard tests are expected to PASS both before and after.
"""

import pytest

from character_canon import (
    ALL_CHARACTERS,
    ARIN,
    ARTHUR,
    CONTRADICTION,
    KAEL,
    MIRA,
    NORA,
    SHEIKH,
    SUPPORTED,
    UNCERTAIN,
    VALID_NEW_ADDITION,
    SpyJudge,
    classify,
)
from continuity_checker.nli_comparator import NLIComparator

pytestmark = pytest.mark.model

MODEL_NAME = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


@pytest.fixture(scope="module")
def nli():
    return NLIComparator.from_pretrained(MODEL_NAME)


def run(nli, text, facts, judge_approves=True):
    judge = SpyJudge(approves=judge_approves)
    return classify(text, facts, nli, judge), judge


# ---- the false flags ----

@pytest.mark.parametrize("text", ["Kael had a pack mule.", "Kael had a mule."])
def test_a_mule_is_not_a_contradiction_of_hair_eye_colour_or_magic(nli, text):
    result, _ = run(nli, text, KAEL)

    assert result.classification != CONTRADICTION
    assert not {"kael-hair-color", "kael-eye-color", "kael-magic-ability"} & set(result.evidence_ids)


def test_stopping_at_once_is_not_a_contradiction_of_magic_ability(nli):
    result, _ = run(nli, "Mira stopped at once.", MIRA)

    assert result.classification != CONTRADICTION
    assert "mira-magic-ability" not in result.evidence_ids


def test_brushing_moss_is_not_uncertain_because_of_occupation(nli):
    result, _ = run(nli, "Kael brushed moss from the road.", KAEL)

    assert "kael-occupation" not in result.evidence_ids


def test_a_remark_by_the_king_is_not_uncertain_because_of_goal_flaw_or_magic(nli):
    result, _ = run(nli, "King Arthur said 'Enough.'", ARTHUR)

    assert not {"arthur-goal", "arthur-flaw", "arthur-magic-ability"} & set(result.evidence_ids)


def test_a_bird_startling_from_a_pine_is_a_new_addition_when_the_judge_approves(nli):
    result, judge = run(nli, "A bird startled from a nearby pine.", ALL_CHARACTERS, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


def test_a_bird_startling_from_a_pine_stays_uncertain_when_the_judge_declines(nli):
    result, _ = run(nli, "A bird startled from a nearby pine.", ALL_CHARACTERS, judge_approves=False)

    assert result.classification == UNCERTAIN


# ---- guards: real conflicts must keep working ----

def test_the_wrong_eye_colour_is_still_a_contradiction(nli):
    result, _ = run(nli, "Kael has blue eyes.", KAEL)

    assert result.classification == CONTRADICTION
    assert "kael-eye-color" in result.evidence_ids


def test_the_wrong_hair_colour_is_still_a_contradiction(nli):
    result, _ = run(nli, "Kael has red hair.", KAEL)

    assert result.classification == CONTRADICTION
    assert "kael-hair-color" in result.evidence_ids


def test_casting_a_spell_when_magic_ability_is_none_is_still_a_contradiction(nli):
    result, _ = run(nli, "Kael cast a fire spell.", KAEL)

    assert result.classification == CONTRADICTION
    assert "kael-magic-ability" in result.evidence_ids


def test_a_silver_sword_against_a_golden_spear_stays_uncertain(nli):
    result, _ = run(nli, "Arin drew a silver sword.", ARIN)

    assert result.classification == UNCERTAIN
    assert result.evidence_ids == ["arin-weapon"]


def test_a_named_entity_missing_from_canon_stays_uncertain_even_if_the_judge_would_approve(nli):
    result, _ = run(nli, "Madame Orlova runs the fish market.", ALL_CHARACTERS, judge_approves=True)

    assert result.classification == UNCERTAIN


# ---- false SUPPORT ----

@pytest.mark.parametrize(
    "text, facts, unrelated",
    [
        ("Nora stepped closer.", NORA, {"nora-build"}),
        ("Nora ran.", NORA, {"nora-appearance"}),
        ("Kael ran.", KAEL, {"kael-flaw"}),
        ("Kael followed the path.", KAEL, {"kael-flaw", "kael-background"}),
        ("King Arthur ran.", ARTHUR, {"arthur-role", "arthur-leadership-style"}),
        ("King Arthur followed the path.", ARTHUR, {"arthur-background"}),
    ],
)
def test_a_plain_action_is_not_supported_by_facts_it_is_not_about(nli, text, facts, unrelated):
    result, _ = run(nli, text, facts)

    assert result.classification != SUPPORTED
    assert not unrelated & set(result.evidence_ids)


@pytest.mark.parametrize(
    "text, facts, cited",
    [
        ("Nora is lean.", NORA, "nora-build"),
        ("Nora has hazel eyes.", NORA, "nora-eye-color"),
        ("Nora is a scout.", NORA, "nora-occupation"),
        ("Sheikh Idris is still living.", SHEIKH, "sheikh-status"),
    ],
)
def test_a_claim_that_restates_a_fact_is_still_supported_by_it(nli, text, facts, cited):
    result, _ = run(nli, text, facts)

    assert result.classification == SUPPORTED
    assert cited in result.evidence_ids


# ---- scenery that opens with an ordinary noun ----

def test_an_unnamed_someone_in_the_background_is_a_new_addition_when_the_judge_approves(nli):
    result, judge = run(nli, "Someone had tended the lock.", NORA, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


@pytest.mark.parametrize(
    "text", ["Moss blurred the bridge's edges.", "Cracks split the stones of the bridge."]
)
def test_scenery_that_opens_with_an_ordinary_noun_is_a_new_addition_when_the_judge_approves(nli, text):
    result, judge = run(nli, text, ALL_CHARACTERS + NORA, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


@pytest.mark.parametrize(
    "text", ["A bird called overhead.", "The bridge was narrow.", "The bridge was timeworn."]
)
def test_scenery_that_opens_with_a_determiner_is_already_a_new_addition(nli, text):
    result, judge = run(nli, text, ALL_CHARACTERS + NORA, judge_approves=True)

    assert judge.calls
    assert result.classification == VALID_NEW_ADDITION
