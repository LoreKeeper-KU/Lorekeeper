# Authored by Faris
from collections.abc import Callable

from pydantic import BaseModel

from continuity_checker.models import Claim, Scene, SourceSpan


class ProposedClaim(BaseModel):
    """An atomic claim as proposed, with the exact scene words it came from."""

    text: str
    quote: str


class ClaimProposals(BaseModel):
    """Top-level object for structured output, which must be an object, not a list."""

    claims: list[ProposedClaim]


Proposer = Callable[[str], list[ProposedClaim]]

SYSTEM_PROMPT = """\
You extract factual claims from a passage of fiction so they can be checked \
against the story world's established facts.

Rules:
1. Each claim states exactly ONE fact. Split sentences that contain several \
facts (for example, "she raised her hands and summoned fire" is two claims).
2. Write each claim as a self-contained statement. Replace pronouns with \
names ("Amina raised her hands.", not "She raised her hands.").
3. Only extract facts about the story world: characters, abilities, \
relationships, places, objects, events. Skip style, mood and opinion.
4. For each claim, give a quote: the shortest passage of the scene that \
supports it, copied EXACTLY, character for character, as one contiguous \
piece. Never paraphrase, reorder or fix punctuation in a quote.
5. Do not judge whether a claim is true or consistent. Only extract.
6. If the passage has no factual claims, return an empty list.
"""


def locate_span(text: str, quote: str) -> SourceSpan:
    """Find the exact offsets of quote in text (first occurrence)."""
    start = text.find(quote)
    if start == -1:
        raise ValueError(f"Quote not found in scene text: {quote!r}")
    return SourceSpan(start=start, end=start + len(quote))


class ClaimExtractor:
    def __init__(self, proposer: Proposer):
        self.proposer = proposer

    def extract(self, scene: Scene) -> list[Claim]:
        proposals = self.proposer(scene.text)
        return [
            Claim(
                claim_id=f"C{number:03d}",
                text=proposal.text,
                source_span=locate_span(scene.text, proposal.quote),
            )
            for number, proposal in enumerate(proposals, start=1)
        ]


class LLMClaimProposer:
    """Proposes atomic claims with an LLM; the client is injected, so no network in tests."""

    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def __call__(self, text: str) -> list[ProposedClaim]:
        response = self.client.chat.completions.parse(
            model=self.model,
            temperature=0,
            response_format=ClaimProposals,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        message = response.choices[0].message
        if message.parsed is None:
            raise ValueError(f"Model refused or returned no claims object: {message.refusal}")
        return message.parsed.claims


class SharedClientClaimProposer:
    """Proposes claims through the team's shared AIClient.generate_structured.

    The client is injected, so tests pass a fake. Quote checking and offsets stay in
    ClaimExtractor; this class only turns the structured result into a claim list.
    """

    def __init__(self, client):
        self.client = client

    def __call__(self, text: str) -> list[ProposedClaim]:
        return self.client.generate_structured(SYSTEM_PROMPT, text, ClaimProposals).claims


def default_claim_proposer() -> SharedClientClaimProposer:
    """Build the proposer on a real AIClient; raises AIClientError if AI_API_KEY is missing."""
    from shared.ai_client import AIClient  # imported here so the module loads without it

    return SharedClientClaimProposer(AIClient())


def extract_claims(scene: Scene, client, model: str) -> list[Claim]:
    return ClaimExtractor(LLMClaimProposer(client, model)).extract(scene)
