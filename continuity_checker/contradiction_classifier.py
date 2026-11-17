# Authored by Faris
from collections.abc import Callable
from typing import Optional

from continuity_checker.canon_verifier import ClaimComparison, Verdict, fact_to_premise
from continuity_checker.models import CanonFact, Claim, ClaimClassification, VerifiedClaim
from continuity_checker.predicate_policy import is_exclusive


def _describe(fact_ids: list[str], canon_evidence: list[CanonFact]) -> str:
    by_id = {fact.id: fact for fact in canon_evidence}
    return "; ".join(f"{fact_id} ({fact_to_premise(by_id[fact_id])})" for fact_id in fact_ids)


AdditionJudge = Callable[[Claim, list[CanonFact]], bool]
Exclusivity = Callable[[CanonFact], bool]


class ContradictionClassifier:
    """LoreKeeper policy layer: turns an evidence comparison into one of four categories.

    An NLI conflict only counts as a Contradiction when the conflicting fact is exclusive
    (it rules out other values); a conflict with a non-exclusive fact stays Uncertain.
    A neutral comparison is Uncertain unless the injected addition_judge approves it
    and there is canon evidence to judge it against.
    """

    def __init__(
        self,
        addition_judge: Optional[AdditionJudge] = None,
        exclusive: Exclusivity = is_exclusive,
    ):
        self.addition_judge = addition_judge
        self.exclusive = exclusive

    def classify(
        self, claim: Claim, comparison: ClaimComparison, canon_evidence: list[CanonFact]
    ) -> VerifiedClaim:
        base = dict(claim_id=claim.claim_id, text=claim.text, source_span=claim.source_span)

        by_id = {fact.id: fact for fact in canon_evidence}
        conflicts = comparison.conflicting_fact_ids
        accepted = [fact_id for fact_id in conflicts if self.exclusive(by_id[fact_id])]

        verdict = comparison.verdict
        if verdict == Verdict.CONTRADICTION and not accepted:
            # The NLI model saw a conflict, but no conflicting fact rules out other values.
            verdict = Verdict.ENTAILMENT if comparison.supporting_fact_ids else Verdict.NEUTRAL

        if verdict == Verdict.CONTRADICTION:
            return VerifiedClaim(
                **base,
                classification=ClaimClassification.CONTRADICTION,
                evidence_ids=accepted,
                explanation=f"Conflicts with canon fact {_describe(accepted, canon_evidence)}.",
                suggested_action=(
                    "Revise this passage so it no longer conflicts with canon fact "
                    f"{', '.join(accepted)}."
                ),
            )

        if verdict == Verdict.ENTAILMENT:
            ids = comparison.supporting_fact_ids
            return VerifiedClaim(
                **base,
                classification=ClaimClassification.SUPPORTED,
                evidence_ids=ids,
                explanation=f"Supported by canon fact {_describe(ids, canon_evidence)}.",
            )

        if conflicts:
            return VerifiedClaim(
                **base,
                classification=ClaimClassification.UNCERTAIN,
                evidence_ids=conflicts,
                explanation=(
                    f"Possible conflict with canon fact {_describe(conflicts, canon_evidence)}, "
                    "but a fact is not necessarily exclusive, so it is not accepted "
                    "as a contradiction."
                ),
            )

        if canon_evidence and self.addition_judge and self.addition_judge(claim, canon_evidence):
            return VerifiedClaim(
                **base,
                classification=ClaimClassification.VALID_NEW_ADDITION,
                explanation=(
                    "Not covered by canon and no conflict was found; "
                    "a candidate addition that needs user approval."
                ),
            )

        reason = (
            "The retrieved canon evidence neither supports nor contradicts this claim."
            if canon_evidence
            else "No canon evidence was available for this claim."
        )
        return VerifiedClaim(
            **base,
            classification=ClaimClassification.UNCERTAIN,
            explanation=f"{reason} Absence of evidence does not make a claim valid.",
        )
