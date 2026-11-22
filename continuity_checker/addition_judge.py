# Authored by Faris
"""AdditionJudge: is a neutral claim a safe candidate for a Valid New Addition?

Only called by ContradictionClassifier for a claim that no canon fact supports and that
has no accepted contradiction: with the related canon facts, or, for anonymous scenery that
no fact is about, with the scene's whole canon (judge_unrelated). The judge still defaults to
"no": only an explicit valid_new_addition verdict approves, and the result is a candidate for
user approval, never new canon.
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

Choose exactly one verdict.

valid_new_addition. Choose it when ALL of these hold:
- the claim adds a concrete new detail: an event, an interaction, or a background \
detail;
- no shown fact conflicts with it or is in tension with it, even by implication;
- it does not change or assert a core attribute of a character (whether alive or \
dead, abilities, species, family, allegiance, house) or a rule of the world;
- it adds no unestablished superlative or qualifier (see insufficient_context).
The number of shown facts does not matter. A harmless event, interaction or \
background detail about an established character or place is valid_new_addition even \
when only one fact is shown, because it conflicts with nothing shown and settles \
nothing that canon fixes. New details are not supposed to be verifiable from canon.

conflicts_or_tension. A shown fact conflicts with the claim or sits in tension with it.

insufficient_context. Choose it ONLY when the claim:
- changes or asserts a core attribute or relationship that the shown facts do not \
settle (for example a new sibling, child, parent, house or allegiance);
- changes a rule of the world;
- adds an unestablished superlative or qualifier such as "best", "greatest", \
"largest", "only" or "first";
- or genuinely cannot be judged from the shown facts, because what it says depends \
on something canon would have to state.
Having few facts is not, by itself, a reason to choose insufficient_context.

The absence of a contradicting fact is not enough on its own: the claim must also \
meet every condition under valid_new_addition. Explain your reasoning briefly, naming \
the rule that applies, then give the verdict.
"""


# Used only for scenery that no canon fact is about (see scene_detail.py). It is a separate prompt
# so that ADDITION_SYSTEM_PROMPT, whose hash the evaluation results record, stays as evaluated.
SCENERY_SYSTEM_PROMPT = """\
You decide whether a new claim from a generated story scene can be offered to the \
author as a candidate addition to the story world.

The claim is an anonymous scene detail: no canon fact states it and it names no established \
character or place. You are given the established canon of the characters in this scene; none \
of it is about this claim. Judge ONLY against the facts shown; never invent canon.

Choose exactly one verdict.

valid_new_addition. Choose it when ALL of these hold:
- the claim adds a concrete, harmless detail about the setting or atmosphere: weather, terrain, \
objects, animals, sounds, light, or a passing bystander;
- no shown fact conflicts with it or is in tension with it, even by implication (for example a \
magical event when canon says a character has no magic);
- it does not change a rule of the world or a core attribute of a character, and adds no \
unestablished superlative such as "best", "largest" or "only".
That no shown fact is about the claim is expected for scenery and is not a reason to decline.

conflicts_or_tension. A shown fact conflicts with the claim or sits in tension with it, even by \
implication.

insufficient_context. Choose it ONLY when the claim names a specific person, place or \
organisation that the canon does not contain; changes a rule of the world or a core attribute; \
adds an unestablished superlative; or genuinely cannot be judged from the facts shown.

Explain your reasoning briefly, naming the rule that applies, then give the verdict.
"""


class LLMAdditionJudge:
    """AdditionJudge backed by the shared AIClient; the client is injected for tests."""

    def __init__(self, client):
        self.client = client

    def judge_unrelated(self, claim: Claim, world_facts: list[CanonFact]) -> bool:
        """Judge scenery no fact is about against the scene's whole canon; default-deny."""
        if not world_facts:
            return False
        facts = "\n".join(f"- {fact.id}: {fact_to_premise(fact)}" for fact in world_facts)
        prompt = (
            f"Claim: {claim.text}\n\n"
            f"Established canon of this scene (none of it is about this claim):\n{facts}"
        )
        decision = self.client.generate_structured(SCENERY_SYSTEM_PROMPT, prompt, AdditionDecision)
        return decision.verdict == AdditionVerdict.VALID_NEW_ADDITION

    def __call__(self, claim: Claim, canon_evidence: list[CanonFact]) -> bool:
        if not canon_evidence:
            return False  # nothing to judge against, so nothing can be called safe
        facts = "\n".join(f"- {fact.id}: {fact_to_premise(fact)}" for fact in canon_evidence)
        prompt = f"Claim: {claim.text}\n\nRelated canon facts:\n{facts}"
        decision = self.client.generate_structured(ADDITION_SYSTEM_PROMPT, prompt, AdditionDecision)
        return decision.verdict == AdditionVerdict.VALID_NEW_ADDITION
