"""AdditionJudge: is a neutral claim a safe candidate for a Valid New Addition?

Only called by ContradictionClassifier for a claim that no canon fact supports and that
has no accepted contradiction, and only when canon evidence exists. The judge still
defaults to "no": only an explicit valid_new_addition verdict approves, and the result
is a candidate for user approval, never new canon.
"""

from enum import Enum

from pydantic import BaseModel

from continuity_checker.canon_verifier import fact_to_premise
from continuity_checker.models import CanonFact, Claim


class AdditionVerdict(str, Enum):
    VALID_NEW_ADDITION = "valid_new_addition"
    CONFLICTS_OR_TENSION = "conflicts_or_tension"
    INSUFFICIENT_CONTEXT = "insufficient_context"


class AdditionDecision(BaseModel):
    """Structured output; the reasoning comes first so the model thinks before it decides."""

    reasoning: str
    verdict: AdditionVerdict


ADDITION_SYSTEM_PROMPT = """\
You decide whether a new claim from a generated story scene can be offered to the \
author as a candidate addition to the story world.

You are given one claim and the established canon facts that seem related to it. \
The claim is not stated by any of these facts. Judge ONLY against the facts shown; \
never invent canon.

Choose exactly one verdict:
- valid_new_addition: the claim adds a concrete new detail or event, AND no shown \
fact conflicts with it or is in tension with it (even by implication), AND it does \
not change a character's core attributes (whether alive or dead, abilities, species, \
family, allegiance) or the rules of the world.
- conflicts_or_tension: a shown fact conflicts with the claim, or sits in tension \
with it.
- insufficient_context: the shown facts are too thin to judge safely, or the claim \
touches a core attribute or world rule that the shown facts do not settle.

The absence of a contradicting fact is not enough on its own. If you are unsure, \
choose insufficient_context. Explain your reasoning briefly, then give the verdict.
"""


class LLMAdditionJudge:
    """AdditionJudge backed by the shared AIClient; the client is injected for tests."""

    def __init__(self, client):
        self.client = client

    def __call__(self, claim: Claim, canon_evidence: list[CanonFact]) -> bool:
        if not canon_evidence:
            return False  # nothing to judge against, so nothing can be called safe
        facts = "\n".join(f"- {fact.id}: {fact_to_premise(fact)}" for fact in canon_evidence)
        prompt = f"Claim: {claim.text}\n\nRelated canon facts:\n{facts}"
        decision = self.client.generate_structured(ADDITION_SYSTEM_PROMPT, prompt, AdditionDecision)
        return decision.verdict == AdditionVerdict.VALID_NEW_ADDITION
