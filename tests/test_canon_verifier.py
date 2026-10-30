from continuity_checker.canon_verifier import Verdict, compare_claim, fact_to_premise
from continuity_checker.models import CanonFact, Claim, SourceSpan


def make_claim():
    return Claim(
        claim_id="C001",
        text="Amina can summon magical firestorms.",
        source_span=SourceSpan(start=0, end=10),
    )


def make_fact(fact_id):
    return CanonFact(
        id=fact_id,
        subject="char_amina",
        predicate="magic_ability",
        object="none",
    )


def scripted(verdicts):
    """A fake comparator: returns the scripted verdict for each fact_id."""

    def comparator(claim, fact):
        return verdicts[fact.id]

    return comparator


def compare(verdicts):
    facts = [make_fact(fact_id) for fact_id in verdicts]
    return compare_claim(make_claim(), facts, scripted(verdicts))


def test_no_evidence_is_neutral_with_no_cited_facts():
    result = compare_claim(make_claim(), [], scripted({}))
    assert result.verdict == Verdict.NEUTRAL
    assert result.supporting_fact_ids == []
    assert result.conflicting_fact_ids == []


def test_all_neutral_facts_stay_neutral():
    result = compare({"F001": Verdict.NEUTRAL, "F002": Verdict.NEUTRAL})
    assert result.verdict == Verdict.NEUTRAL


def test_an_entailing_fact_makes_the_claim_entailed_and_is_cited():
    result = compare({"F001": Verdict.NEUTRAL, "F002": Verdict.ENTAILMENT})
    assert result.verdict == Verdict.ENTAILMENT
    assert result.supporting_fact_ids == ["F002"]


def test_a_contradicting_fact_makes_the_claim_contradicted_and_is_cited():
    result = compare({"F001": Verdict.NEUTRAL, "F002": Verdict.CONTRADICTION})
    assert result.verdict == Verdict.CONTRADICTION
    assert result.conflicting_fact_ids == ["F002"]


def test_contradiction_outranks_entailment_and_both_are_cited():
    result = compare({"F001": Verdict.ENTAILMENT, "F002": Verdict.CONTRADICTION})
    assert result.verdict == Verdict.CONTRADICTION
    assert result.supporting_fact_ids == ["F001"]
    assert result.conflicting_fact_ids == ["F002"]


def test_comparator_is_called_once_per_fact_with_the_claim_and_that_fact():
    calls = []

    def comparator(claim, fact):
        calls.append((claim.claim_id, fact.id))
        return Verdict.NEUTRAL

    compare_claim(make_claim(), [make_fact("F001"), make_fact("F002")], comparator)
    assert calls == [("C001", "F001"), ("C001", "F002")]


def test_claim_comparison_carries_the_claim_id():
    assert compare({"F001": Verdict.NEUTRAL}).claim_id == "C001"


def test_premise_for_the_amina_fact_reads_as_a_plain_statement():
    assert fact_to_premise(make_fact("F002")) == "char amina magic ability: none"


def test_premise_keeps_the_object_verbatim():
    fact = CanonFact(
        id="F003",
        subject="char_amina",
        predicate="rules",
        object="Northern_Kingdom",
    )
    assert fact_to_premise(fact) == "char amina rules: Northern_Kingdom"
