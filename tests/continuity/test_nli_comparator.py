# Authored by Faris
import pytest

from continuity_checker.canon_verifier import Verdict
from continuity_checker.nli_comparator import NLIComparator
from continuity_checker.models import CanonFact, Claim, SourceSpan

CLAIM = Claim(
    claim_id="C001",
    text="Amina can summon magical firestorms.",
    source_span=SourceSpan(start=0, end=10),
)
FACT = CanonFact(
    id="F002", subject="char_amina", predicate="magic_ability",
    object="none",
)
MODEL_ORDER = ["entailment", "neutral", "contradiction"]


def comparator(probabilities, labels=MODEL_ORDER, **thresholds):
    return NLIComparator(lambda premise, hypothesis: probabilities, labels, **thresholds)


def test_scorer_receives_the_fact_premise_and_the_claim_as_hypothesis():
    seen = []

    def scorer(premise, hypothesis):
        seen.append((premise, hypothesis))
        return [0.1, 0.8, 0.1]

    NLIComparator(scorer, MODEL_ORDER)(CLAIM, FACT)

    assert seen == [("char amina magic ability: none", "Amina can summon magical firestorms.")]


@pytest.mark.parametrize(
    "probabilities, expected",
    [
        ([0.05, 0.05, 0.90], Verdict.CONTRADICTION),
        ([0.90, 0.05, 0.05], Verdict.ENTAILMENT),
        ([0.10, 0.80, 0.10], Verdict.NEUTRAL),
    ],
)
def test_the_dominant_probability_decides_the_verdict(probabilities, expected):
    assert comparator(probabilities)(CLAIM, FACT) == expected


def test_probabilities_are_matched_to_labels_by_name_not_by_position():
    other_order = ["contradiction", "entailment", "neutral"]
    assert comparator([0.90, 0.05, 0.05], other_order)(CLAIM, FACT) == Verdict.CONTRADICTION
    assert comparator([0.05, 0.90, 0.05], other_order)(CLAIM, FACT) == Verdict.ENTAILMENT


def test_label_names_are_case_insensitive():
    upper = ["ENTAILMENT", "NEUTRAL", "CONTRADICTION"]
    assert comparator([0.05, 0.05, 0.90], upper)(CLAIM, FACT) == Verdict.CONTRADICTION


def test_a_contradiction_below_its_threshold_is_not_reported():
    probabilities = [0.30, 0.25, 0.45]
    assert comparator(probabilities)(CLAIM, FACT) == Verdict.NEUTRAL
    assert comparator(probabilities, contradiction_threshold=0.4)(CLAIM, FACT) == Verdict.CONTRADICTION


def test_an_entailment_below_its_threshold_is_not_reported():
    probabilities = [0.45, 0.30, 0.25]
    assert comparator(probabilities)(CLAIM, FACT) == Verdict.NEUTRAL
    assert comparator(probabilities, entailment_threshold=0.4)(CLAIM, FACT) == Verdict.ENTAILMENT


def test_contradiction_wins_when_both_thresholds_are_met():
    result = comparator(
        [0.40, 0.20, 0.40], contradiction_threshold=0.3, entailment_threshold=0.3
    )(CLAIM, FACT)
    assert result == Verdict.CONTRADICTION


def test_labels_must_be_exactly_the_three_nli_labels():
    with pytest.raises(ValueError, match="labels"):
        NLIComparator(lambda p, h: [0.5, 0.5], ["entailment", "contradiction"])
    with pytest.raises(ValueError, match="labels"):
        NLIComparator(lambda p, h: [1, 0, 0], ["entailment", "neutral", "maybe"])


def test_a_scorer_returning_the_wrong_number_of_probabilities_is_rejected():
    with pytest.raises(ValueError, match="probabilities"):
        comparator([0.5, 0.5])(CLAIM, FACT)
