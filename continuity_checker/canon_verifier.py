# Authored by Faris
from collections.abc import Callable
from enum import Enum

from pydantic import BaseModel

from continuity_checker.models import CanonFact, Claim, Scene, VerificationReport, VerifiedClaim
from continuity_checker.relevance import select_relevant_facts
from continuity_checker.report_builder import build_report


class Verdict(str, Enum):
    """Evidence-comparison layer. Not the same as the LoreKeeper Classification."""

    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


Comparator = Callable[[Claim, CanonFact], Verdict]
Relevance = Callable[[Claim, list[CanonFact]], list[CanonFact]]


def fact_to_premise(fact: CanonFact) -> str:
    """Turn a fact triple into text for an NLI model.

    Isolated on purpose: replace with a natural-language statement field if the team adds one.
    """
    subject = fact.subject.replace("_", " ")
    predicate = fact.predicate.replace("_", " ")
    return f"{subject} {predicate}: {fact.object}"


class ClaimComparison(BaseModel):
    claim_id: str
    verdict: Verdict
    supporting_fact_ids: list[str]
    conflicting_fact_ids: list[str]


def compare_claim(
    claim: Claim, canon_evidence: list[CanonFact], comparator: Comparator
) -> ClaimComparison:
    """Compare a claim with every fact; contradiction > entailment > neutral."""
    verdicts = [(fact.id, comparator(claim, fact)) for fact in canon_evidence]
    supporting = [fact_id for fact_id, v in verdicts if v == Verdict.ENTAILMENT]
    conflicting = [fact_id for fact_id, v in verdicts if v == Verdict.CONTRADICTION]

    if conflicting:
        verdict = Verdict.CONTRADICTION
    elif supporting:
        verdict = Verdict.ENTAILMENT
    else:
        verdict = Verdict.NEUTRAL

    return ClaimComparison(
        claim_id=claim.claim_id,
        verdict=verdict,
        supporting_fact_ids=supporting,
        conflicting_fact_ids=conflicting,
    )


class CanonVerifier:
    """Wires extraction, evidence comparison and classification.

    Each claim is compared (and classified) against only the facts that `relevance`
    selects, so unrelated facts cannot produce false contradictions.
    """

    def __init__(
        self,
        extractor,
        comparator: Comparator,
        classifier,
        relevance: Relevance = select_relevant_facts,
    ):
        self.extractor = extractor
        self.comparator = comparator
        self.classifier = classifier
        self.relevance = relevance

    def verify_claim(self, claim: Claim, canon_evidence: list[CanonFact]) -> VerifiedClaim:
        relevant = self.relevance(claim, canon_evidence)
        comparison = compare_claim(claim, relevant, self.comparator)
        return self.classifier.classify(claim, comparison, relevant)

    def verify_claims(self, scene: Scene, canon_evidence: list[CanonFact]) -> list[VerifiedClaim]:
        """Detailed results, including claim IDs and source spans (internal use)."""
        claims = self.extractor.extract(scene)
        return [self.verify_claim(claim, canon_evidence) for claim in claims]

    def verify_scene(self, scene: Scene, canon_evidence: list[CanonFact]) -> VerificationReport:
        return build_report(self.verify_claims(scene, canon_evidence))
