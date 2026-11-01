"""Claim extraction through the shared AIClient (no real API calls).

Most tests inject a fake client with the one method the adapter uses. One test runs the
real shared AIClient against a tiny local fake server, to prove the two fit together.
"""

import pytest

from continuity_checker.claim_extractor import (
    SYSTEM_PROMPT,
    ClaimExtractor,
    ClaimProposals,
    ProposedClaim,
    SharedClientClaimProposer,
    default_claim_proposer,
)
from continuity_checker.models import Scene
from shared import config
from shared.ai_client import AIClient, AIClientError

SENTENCE = "Princess Amina raised her hands and summoned a magical firestorm."


class FakeSharedClient:
    """Stands in for AIClient: only generate_structured, no network."""

    def __init__(self, result=None, error=None):
        self.calls = []
        self._result = result
        self._error = error

    def generate_structured(self, instructions, prompt, schema):
        self.calls.append((instructions, prompt, schema))
        if self._error:
            raise self._error
        return self._result


def amina_proposals():
    return ClaimProposals(
        claims=[
            ProposedClaim(text="Amina raised her hands.", quote="Princess Amina raised her hands"),
            ProposedClaim(text="Amina can summon magical firestorms.", quote=SENTENCE),
        ]
    )


def test_adapter_sends_the_prompt_and_scene_to_generate_structured():
    client = FakeSharedClient(result=amina_proposals())

    SharedClientClaimProposer(client)(SENTENCE)

    assert client.calls == [(SYSTEM_PROMPT, SENTENCE, ClaimProposals)]


def test_adapter_returns_the_claims_inside_the_structured_result():
    client = FakeSharedClient(result=amina_proposals())

    proposed = SharedClientClaimProposer(client)(SENTENCE)

    assert [p.text for p in proposed] == [
        "Amina raised her hands.",
        "Amina can summon magical firestorms.",
    ]


def test_adapter_lets_client_errors_through_instead_of_returning_no_claims():
    client = FakeSharedClient(error=AIClientError("Could not reach the API"))

    with pytest.raises(AIClientError, match="Could not reach"):
        SharedClientClaimProposer(client)(SENTENCE)


def test_extractor_still_builds_ids_and_exact_spans_from_adapter_output():
    scene = Scene(scene_id="s", world_id="w", text=SENTENCE)
    extractor = ClaimExtractor(SharedClientClaimProposer(FakeSharedClient(result=amina_proposals())))

    claims = extractor.extract(scene)

    assert [c.claim_id for c in claims] == ["C001", "C002"]
    first = claims[0].source_span
    assert SENTENCE[first.start : first.end] == "Princess Amina raised her hands"


def test_extractor_still_rejects_a_quote_the_model_invented():
    scene = Scene(scene_id="s", world_id="w", text=SENTENCE)
    invented = ClaimProposals(
        claims=[ProposedClaim(text="Amina is a pirate.", quote="Amina sailed the seas.")]
    )
    extractor = ClaimExtractor(SharedClientClaimProposer(FakeSharedClient(result=invented)))

    with pytest.raises(ValueError, match="not found"):
        extractor.extract(scene)


def test_default_proposer_fails_clearly_when_the_api_key_is_missing(monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", None)

    with pytest.raises(AIClientError, match="AI_API_KEY"):
        default_claim_proposer()


def test_default_proposer_wraps_a_real_shared_client_when_a_key_exists(monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "test-key")

    proposer = default_claim_proposer()

    assert isinstance(proposer, SharedClientClaimProposer)
    assert isinstance(proposer.client, AIClient)


def test_real_shared_client_round_trip_gives_claims_with_exact_spans(fake_chat_api):
    fake_chat_api.reply_text = amina_proposals().model_dump_json()
    scene = Scene(scene_id="s", world_id="w", text=SENTENCE)

    claims = ClaimExtractor(SharedClientClaimProposer(fake_chat_api.client)).extract(scene)

    assert [c.text for c in claims] == [
        "Amina raised her hands.",
        "Amina can summon magical firestorms.",
    ]
    assert SENTENCE[claims[1].source_span.start : claims[1].source_span.end] == SENTENCE
    (request,) = fake_chat_api.requests_seen
    assert SENTENCE in [m["content"] for m in request["messages"]]
    assert SYSTEM_PROMPT in [m["content"] for m in request["messages"]]
