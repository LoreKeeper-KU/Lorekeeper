# Authored by Faris
from collections.abc import Callable, Sequence
from typing import Optional

from continuity_checker.canon_verifier import ClaimComparison, Verdict, fact_to_premise
from continuity_checker.models import CanonFact, Claim, ClaimClassification, VerifiedClaim
from continuity_checker.predicate_policy import (
    is_exclusive,
    mentions_topic,
    refers_to_attribute,
    supports_topic,
)
from continuity_checker.scene_detail import is_scene_detail


def _describe(fact_ids: list[str], canon_evidence: list[CanonFact]) -> str:
    by_id = {fact.id: fact for fact in canon_evidence}
    return "; ".join(f"{fact_id} ({fact_to_premise(by_id[fact_id])})" for fact_id in fact_ids)


AdditionJudge = Callable[[Claim, list[CanonFact]], bool]
Exclusivity = Callable[[CanonFact], bool]
AttributeCheck = Callable[[str, CanonFact], bool]  # (claim text, fact) -> is the claim about it
SceneCheck = Callable[[str], bool]  # claim text -> is it anonymous scenery


class ContradictionClassifier:
    """LoreKeeper policy layer: turns an evidence comparison into one of four categories.

    An NLI conflict or entailment is only evidence when the claim is about what the fact
    states; one with a fact the claim is not about is NLI noise and is ignored. A real conflict
    with an exclusive fact (it rules out other values) is a Contradiction; one with a
    non-exclusive fact stays Uncertain; real entailment is Supported. A neutral comparison is Uncertain unless the injected addition_judge
    approves it. The judge sees the related canon facts; for anonymous scenery that no fact is
    about (scene_detail.py) it sees the scene's whole canon instead (`world_facts`), through its
    `judge_unrelated` method if it has one. Anything that names someone canon does not contain,
    or does not read as scenery, is never judged without related facts.
    """

    def __init__(
        self,
        addition_judge: Optional[AdditionJudge] = None,
        exclusive: Exclusivity = is_exclusive,
        refers_to_attribute: AttributeCheck = refers_to_attribute,
        mentions_topic: AttributeCheck = mentions_topic,
        is_scene_detail: SceneCheck = is_scene_detail,
        supports_topic: AttributeCheck = supports_topic,
    ):
        self.addition_judge = addition_judge
        self.exclusive = exclusive
        self.refers_to_attribute = refers_to_attribute
        self.mentions_topic = mentions_topic
        self.is_scene_detail = is_scene_detail
        self.supports_topic = supports_topic

    def _is_supported_by(self, claim: Claim, fact: CanonFact) -> bool:
        # Exclusive facts (status, species, family...) are open-ended, so only the attributes
        # with cue words are checked; every other fact needs a shared topic word.
        if self.exclusive(fact):
            return self.refers_to_attribute(claim.text, fact)
        return self.supports_topic(claim.text, fact)

    def _approves_scenery(
        self, claim: Claim, canon_evidence: list[CanonFact], world_facts: list[CanonFact]
    ) -> bool:
        if canon_evidence or not world_facts or not self.addition_judge:
            return False
        if not self.is_scene_detail(claim.text):
            return False
        judge = getattr(self.addition_judge, "judge_unrelated", self.addition_judge)
        return bool(judge(claim, list(world_facts)))

    def _is_about(self, claim: Claim, fact: CanonFact) -> bool:
        if self.exclusive(fact):
            return self.refers_to_attribute(claim.text, fact)
        return self.mentions_topic(claim.text, fact)

    def classify(
        self,
        claim: Claim,
        comparison: ClaimComparison,
        canon_evidence: list[CanonFact],
        world_facts: Sequence[CanonFact] = (),
    ) -> VerifiedClaim:
        base = dict(claim_id=claim.claim_id, text=claim.text, source_span=claim.source_span)

        by_id = {fact.id: fact for fact in canon_evidence}
        # A conflict with a fact the claim is not about ("Kael had a mule" against hair_color,
        # "Kael brushed moss" against occupation) is the NLI model guessing, not evidence: drop
        # it before it is cited, so it can neither contradict nor keep the claim Uncertain.
        conflicts = [
            fact_id
            for fact_id in comparison.conflicting_fact_ids
            if self._is_about(claim, by_id[fact_id])
        ]
        accepted = [fact_id for fact_id in conflicts if self.exclusive(by_id[fact_id])]
        # Likewise "Nora stepped closer" is not supported by `build: lean`, however the NLI
        # model scored it: only facts the claim is about can support it.
        supporting = [
            fact_id
            for fact_id in comparison.supporting_fact_ids
            if self._is_supported_by(claim, by_id[fact_id])
        ]

        verdict = comparison.verdict
        if verdict == Verdict.CONTRADICTION and not accepted:
            # The NLI model saw a conflict, but no conflicting fact rules out other values.
            verdict = Verdict.ENTAILMENT if supporting else Verdict.NEUTRAL
        elif verdict == Verdict.ENTAILMENT and not supporting:
            verdict = Verdict.NEUTRAL

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
            ids = supporting
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

        if self._approves_scenery(claim, canon_evidence, world_facts):
            return VerifiedClaim(
                **base,
                classification=ClaimClassification.VALID_NEW_ADDITION,
                explanation=(
                    "A scene detail that no canon fact is about, and none of the scene's canon "
                    "conflicts with it; a candidate addition that needs user approval."
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
