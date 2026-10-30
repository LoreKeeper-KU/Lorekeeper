from continuity_checker.canon_verifier import ClaimComparison, Verdict
from continuity_checker.contradiction_classifier import ContradictionClassifier
from continuity_checker.models import CanonFact, Claim, ClaimClassification, SourceSpan


def make_claim():
    return Claim(
        claim_id="C001",
        text="Amina can summon magical firestorms.",
        source_span=SourceSpan(start=20, end=70),
    )


def make_fact(fact_id, predicate="magic_ability", value="none"):
    return CanonFact(
        id=fact_id,
        subject="char_amina",
        predicate=predicate,
        object=value,
    )


def comparison(verdict, supporting=(), conflicting=()):
    return ClaimComparison(
        claim_id="C001",
        verdict=verdict,
        supporting_fact_ids=list(supporting),
        conflicting_fact_ids=list(conflicting),
    )


F002 = make_fact("F002")
F003 = make_fact("F003", predicate="rules", value="Northern_Kingdom")


def test_contradiction_cites_the_conflicting_facts_and_keeps_the_claim_and_span():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F002"]), [F002, F003]
    )
    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F002"]
    assert (result.claim_id, result.text) == ("C001", "Amina can summon magical firestorms.")
    assert result.source_span == SourceSpan(start=20, end=70)


def test_contradiction_explanation_cites_the_fact_and_suggests_a_revision():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F002"]), [F002, F003]
    )
    assert "F002" in result.explanation
    assert "char amina magic ability: none" in result.explanation
    assert "F002" in result.suggested_action


def test_entailment_is_supported_and_cites_the_supporting_facts():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.ENTAILMENT, supporting=["F003"]), [F002, F003]
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F003"]
    assert "F003" in result.explanation
    assert "char amina rules: Northern_Kingdom" in result.explanation
    assert result.suggested_action is None


def test_neutral_defaults_to_uncertain_and_never_to_a_new_addition():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002, F003]
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == []
    assert "neither supports nor contradicts" in result.explanation
    assert result.suggested_action is None


def test_neutral_with_no_canon_evidence_says_so():
    result = ContradictionClassifier().classify(make_claim(), comparison(Verdict.NEUTRAL), [])
    assert result.classification == ClaimClassification.UNCERTAIN
    assert "No canon evidence" in result.explanation


def approving(claim, canon_evidence):
    return True


def declining(claim, canon_evidence):
    return False


def must_not_be_called(claim, canon_evidence):
    raise AssertionError("AdditionJudge must only be consulted for neutral claims with evidence")


def test_neutral_becomes_a_new_addition_only_when_the_judge_approves():
    result = ContradictionClassifier(approving).classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002]
    )
    assert result.classification == ClaimClassification.VALID_NEW_ADDITION
    assert result.evidence_ids == []
    assert "approval" in result.explanation


def test_neutral_stays_uncertain_when_the_judge_declines():
    result = ContradictionClassifier(declining).classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002]
    )
    assert result.classification == ClaimClassification.UNCERTAIN


def test_judge_receives_the_claim_and_the_canon_evidence():
    seen = []

    def judge(claim, canon_evidence):
        seen.append((claim.claim_id, [f.id for f in canon_evidence]))
        return False

    ContradictionClassifier(judge).classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002, F003]
    )
    assert seen == [("C001", ["F002", "F003"])]


def test_judge_is_not_consulted_for_contradiction_or_supported_claims():
    classifier = ContradictionClassifier(must_not_be_called)
    contradicted = classifier.classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F002"]), [F002]
    )
    supported = classifier.classify(
        make_claim(), comparison(Verdict.ENTAILMENT, supporting=["F002"]), [F002]
    )
    assert contradicted.classification == ClaimClassification.CONTRADICTION
    assert supported.classification == ClaimClassification.SUPPORTED


def test_no_canon_evidence_stays_uncertain_even_if_the_judge_would_approve():
    result = ContradictionClassifier(approving).classify(
        make_claim(), comparison(Verdict.NEUTRAL), []
    )
    assert result.classification == ClaimClassification.UNCERTAIN


SPEAR = make_fact("F010", predicate="weapon", value="golden spear")
ALIVE = make_fact("F011", predicate="status", value="alive")


def test_a_conflict_with_a_non_exclusive_fact_stays_uncertain_and_cites_it():
    result = ContradictionClassifier(must_not_be_called).classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F010"]), [SPEAR]
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == ["F010"]
    assert "F010" in result.explanation
    assert "not accepted as a contradiction" in result.explanation
    assert result.suggested_action is None


def test_a_conflict_with_an_exclusive_fact_is_still_a_contradiction():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F011"]), [ALIVE]
    )
    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F011"]


def test_only_the_exclusive_facts_are_cited_when_conflicts_are_mixed():
    result = ContradictionClassifier().classify(
        make_claim(),
        comparison(Verdict.CONTRADICTION, conflicting=["F010", "F011"]),
        [SPEAR, ALIVE],
    )
    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F011"]


def test_a_rejected_conflict_does_not_overrule_real_support():
    result = ContradictionClassifier().classify(
        make_claim(),
        comparison(Verdict.CONTRADICTION, supporting=["F003"], conflicting=["F010"]),
        [F003, SPEAR],
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F003"]


def test_the_exclusivity_check_can_be_replaced():
    result = ContradictionClassifier(exclusive=lambda fact: True).classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F010"]), [SPEAR]
    )
    assert result.classification == ClaimClassification.CONTRADICTION
