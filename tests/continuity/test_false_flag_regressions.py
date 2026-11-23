# Authored by Faris
"""Harmless scene details must not be flagged, and real conflicts must still be.

Regression tests for the false UNCERTAIN / CONTRADICTION results seen in the integrated app.
They run the real relevance filter, comparison and classifier with a scripted NLI (see
character_canon.py), so they are fast and deterministic. The same cases run against the real
DeBERTa model in test_false_flag_real_model.py.

Written before the fix: the "false flag" tests are expected to FAIL until the continuity logic
is corrected, and the guard tests are expected to PASS both before and after.
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
    ScriptedNLI,
    SpyJudge,
    classify,
)


def run(text, facts, judge_approves=True):
    judge = SpyJudge(approves=judge_approves)
    return classify(text, facts, ScriptedNLI(), judge), judge


# ---- the false flags (these reproduce the reported bugs) ----

@pytest.mark.parametrize("text", ["Kael had a pack mule.", "Kael had a mule."])
def test_a_mule_is_not_a_contradiction_of_hair_eye_colour_or_magic(text):
    result, _ = run(text, KAEL)

    assert result.classification != CONTRADICTION
    assert not {"kael-hair-color", "kael-eye-color", "kael-magic-ability"} & set(result.evidence_ids)


def test_stopping_at_once_is_not_a_contradiction_of_magic_ability():
    result, _ = run("Mira stopped at once.", MIRA)

    assert result.classification != CONTRADICTION
    assert "mira-magic-ability" not in result.evidence_ids


@pytest.mark.parametrize(
    "text, unrelated_facts",
    [
        ("Kael brushed moss from the road.", {"kael-occupation"}),
        ("Kael led the mule forward.", {"kael-role", "kael-background", "kael-occupation"}),
    ],
)
def test_an_ordinary_action_is_not_uncertain_because_of_occupation_or_role(text, unrelated_facts):
    result, _ = run(text, KAEL)

    assert not unrelated_facts & set(result.evidence_ids)


def test_brushing_moss_is_offered_to_the_judge_and_can_be_a_new_addition():
    """Not being stuck on an unrelated fact means the claim reaches the addition judge."""
    result, judge = run("Kael brushed moss from the road.", KAEL, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


def test_a_remark_by_the_king_is_not_uncertain_because_of_goal_flaw_or_magic():
    result, _ = run("King Arthur said 'Enough.'", ARTHUR)

    assert not {"arthur-goal", "arthur-flaw", "arthur-magic-ability"} & set(result.evidence_ids)


def test_a_remark_by_the_king_is_offered_to_the_judge_and_can_be_a_new_addition():
    result, judge = run("King Arthur said 'Enough.'", ARTHUR, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


@pytest.mark.parametrize(
    "text",
    ["A bird startled from a nearby pine.", "The road was half-swallowed by earth and roots."],
)
def test_scenery_with_no_named_entity_is_a_new_addition_when_the_judge_approves(text):
    result, judge = run(text, ALL_CHARACTERS, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


@pytest.mark.parametrize(
    "text",
    ["A bird startled from a nearby pine.", "The road was half-swallowed by earth and roots."],
)
def test_scenery_stays_uncertain_when_the_judge_declines(text):
    """Default-deny is kept: a judge that cannot approve leaves the claim UNCERTAIN."""
    result, _ = run(text, ALL_CHARACTERS, judge_approves=False)

    assert result.classification == UNCERTAIN


# ---- guards: real conflicts must keep working before and after the fix ----

def test_the_wrong_eye_colour_is_still_a_contradiction():
    result, _ = run("Kael has blue eyes.", KAEL)

    assert result.classification == CONTRADICTION
    assert result.evidence_ids == ["kael-eye-color"]


def test_the_wrong_hair_colour_is_still_a_contradiction():
    result, _ = run("Kael has red hair.", KAEL)

    assert result.classification == CONTRADICTION
    assert result.evidence_ids == ["kael-hair-color"]


def test_casting_a_spell_when_magic_ability_is_none_is_still_a_contradiction():
    result, _ = run("Kael cast a fire spell.", KAEL)

    assert result.classification == CONTRADICTION
    assert result.evidence_ids == ["kael-magic-ability"]


def test_a_silver_sword_against_a_golden_spear_stays_uncertain():
    """Weapon is not single-valued, so the conflict is tension, not a contradiction."""
    result, _ = run("Arin drew a silver sword.", ARIN)

    assert result.classification == UNCERTAIN
    assert result.evidence_ids == ["arin-weapon"]


def test_a_named_entity_missing_from_canon_stays_uncertain_even_if_the_judge_would_approve():
    """The frozen labelling policy: an unknown named person or place is never a new addition."""
    result, _ = run("Madame Orlova runs the fish market.", ALL_CHARACTERS, judge_approves=True)

    assert result.classification == UNCERTAIN


# ---- false SUPPORT: a fact the claim is not about must not support it ----

FALSE_SUPPORT = [
    ("Nora stepped closer.", NORA, {"nora-build"}),
    ("Nora ran.", NORA, {"nora-appearance"}),
    ("Kael ran.", KAEL, {"kael-flaw"}),
    ("Kael followed the path.", KAEL, {"kael-flaw", "kael-background"}),
    ("King Arthur ran.", ARTHUR, {"arthur-role", "arthur-leadership-style"}),
    ("King Arthur followed the path.", ARTHUR, {"arthur-background"}),
]


@pytest.mark.parametrize(
    "text, facts, unrelated", FALSE_SUPPORT, ids=[case[0] for case in FALSE_SUPPORT]
)
def test_a_plain_action_is_not_supported_by_facts_it_is_not_about(text, facts, unrelated):
    result, _ = run(text, facts)

    assert result.classification != SUPPORTED
    assert not unrelated & set(result.evidence_ids)


def test_stepping_closer_is_offered_to_the_judge_instead_of_being_supported_by_build():
    """Not being "supported" means the claim is a candidate new addition, judged against canon."""
    result, judge = run("Nora stepped closer.", NORA, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


# ---- guards: real support must keep working before and after the fix ----

@pytest.mark.parametrize(
    "text, facts, cited",
    [
        ("Nora is lean.", NORA, "nora-build"),
        ("Nora has hazel eyes.", NORA, "nora-eye-color"),
        ("Nora is a scout.", NORA, "nora-occupation"),
    ],
)
def test_a_claim_that_restates_a_fact_is_still_supported_by_it(text, facts, cited):
    result, _ = run(text, facts)

    assert result.classification == SUPPORTED
    assert cited in result.evidence_ids


def test_a_paraphrase_of_a_status_fact_is_still_supported_without_a_shared_word():
    """"Still living" shares no word with `status: alive`; a purely word-based check would lose it."""
    result, _ = run("Sheikh Idris is still living.", SHEIKH)

    assert result.classification == SUPPORTED
    assert result.evidence_ids == ["sheikh-status"]


# ---- scenery that opens with an ordinary noun, not only a determiner ----

NOUN_SCENERY = [
    "Moss blurred the bridge's edges.",
    "Cracks split the stones of the bridge.",
    "Shadows pooled under the arch.",
    "Ravens circled overhead.",
    "Stones lay scattered on the path.",
]


@pytest.mark.parametrize("text", NOUN_SCENERY)
def test_scenery_that_opens_with_an_ordinary_noun_is_a_new_addition_when_the_judge_approves(text):
    result, judge = run(text, ALL_CHARACTERS + NORA, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


@pytest.mark.parametrize(
    "text", ["A bird called overhead.", "The bridge was narrow.", "The bridge was timeworn."]
)
def test_scenery_that_opens_with_a_determiner_is_already_a_new_addition(text):
    result, judge = run(text, ALL_CHARACTERS + NORA, judge_approves=True)

    assert judge.calls
    assert result.classification == VALID_NEW_ADDITION


def test_an_unnamed_someone_in_the_background_is_a_new_addition_when_the_judge_approves():
    """Seen live: this single claim kept an otherwise clean scene in needs_review."""
    result, judge = run("Someone had tended the lock.", NORA, judge_approves=True)

    assert judge.calls, "the addition judge was never consulted"
    assert result.classification == VALID_NEW_ADDITION


@pytest.mark.parametrize("text", ["Zayd defended the city.", "Silas defended the city."])
def test_an_unknown_name_at_the_start_is_never_treated_as_scenery(text):
    """Broadening the openers must not let an unknown single-word name through, "-s" names included."""
    result, judge = run(text, ALL_CHARACTERS + NORA, judge_approves=True)

    assert result.classification == UNCERTAIN
    assert judge.calls == []
