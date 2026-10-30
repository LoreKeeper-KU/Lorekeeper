from types import SimpleNamespace

import pytest

from continuity_checker.claim_extractor import (
    ClaimProposals,
    LLMClaimProposer,
    ProposedClaim,
    extract_claims,
)
from continuity_checker.models import Scene

SENTENCE = "Princess Amina raised her hands and summoned a magical firestorm."


class FakeClient:
    """Stands in for openai.OpenAI: only chat.completions.parse, no network."""

    def __init__(self, parsed=None, refusal=None):
        self.calls = []
        self._parsed = parsed
        self._refusal = refusal
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(parsed=self._parsed, refusal=self._refusal)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def amina_proposals():
    return ClaimProposals(
        claims=[
            ProposedClaim(text="Amina raised her hands.", quote=SENTENCE),
            ProposedClaim(text="Amina can summon magical firestorms.", quote=SENTENCE),
        ]
    )


def test_proposer_asks_for_structured_output_with_the_scene_as_user_message():
    client = FakeClient(parsed=amina_proposals())

    LLMClaimProposer(client, model="configured-model")(SENTENCE)

    (call,) = client.calls
    assert call["model"] == "configured-model"
    assert call["temperature"] == 0
    assert call["response_format"] is ClaimProposals
    assert [m["role"] for m in call["messages"]] == ["system", "user"]
    assert call["messages"][1]["content"] == SENTENCE


def test_proposer_returns_the_parsed_claims():
    client = FakeClient(parsed=amina_proposals())
    proposed = LLMClaimProposer(client, model="m")(SENTENCE)
    assert [p.text for p in proposed] == [
        "Amina raised her hands.",
        "Amina can summon magical firestorms.",
    ]


def test_proposer_raises_on_refusal_instead_of_returning_no_claims():
    client = FakeClient(parsed=None, refusal="I can't help with that.")
    with pytest.raises(ValueError, match="refused"):
        LLMClaimProposer(client, model="m")(SENTENCE)


def test_extract_claims_builds_claims_with_ids_and_spans_from_llm_output():
    scene = Scene(scene_id="scene_001", world_id="world_001", text=SENTENCE)
    client = FakeClient(parsed=amina_proposals())

    claims = extract_claims(scene, client, model="m")

    assert [c.claim_id for c in claims] == ["C001", "C002"]
    assert claims[1].text == "Amina can summon magical firestorms."
    span = claims[1].source_span
    assert SENTENCE[span.start : span.end] == SENTENCE
