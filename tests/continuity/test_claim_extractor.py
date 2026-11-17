# Authored by Faris
import pytest

from continuity_checker.claim_extractor import ClaimExtractor, ProposedClaim, locate_span
from continuity_checker.models import Scene

SENTENCE = "Princess Amina raised her hands and summoned a magical firestorm."


def make_scene(text):
    return Scene(scene_id="scene_001", world_id="world_001", text=text)


def test_locate_span_returns_offsets_of_the_quote():
    text = "Amina smiled. Amina summoned fire."
    span = locate_span(text, "Amina summoned fire.")
    assert (span.start, span.end) == (14, 34)
    assert text[span.start : span.end] == "Amina summoned fire."


def test_locate_span_rejects_a_quote_that_is_not_in_the_text():
    with pytest.raises(ValueError, match="not found"):
        locate_span("Amina smiled.", "Amina frowned.")


def test_one_sentence_can_yield_several_atomic_claims():
    def proposer(text):
        return [
            ProposedClaim(text="Amina raised her hands.", quote=SENTENCE),
            ProposedClaim(text="Amina can summon magical firestorms.", quote=SENTENCE),
        ]

    claims = ClaimExtractor(proposer).extract(make_scene(SENTENCE))

    assert [c.claim_id for c in claims] == ["C001", "C002"]
    assert [c.text for c in claims] == [
        "Amina raised her hands.",
        "Amina can summon magical firestorms.",
    ]
    assert claims[0].source_span == claims[1].source_span
    assert SENTENCE[claims[0].source_span.start : claims[0].source_span.end] == SENTENCE


def test_extractor_gives_the_proposer_the_scene_text():
    seen = []

    def proposer(text):
        seen.append(text)
        return []

    ClaimExtractor(proposer).extract(make_scene(SENTENCE))
    assert seen == [SENTENCE]


def test_scene_with_no_claims_yields_an_empty_list():
    assert ClaimExtractor(lambda text: []).extract(make_scene(SENTENCE)) == []


def test_extractor_rejects_a_proposal_that_misquotes_the_scene():
    def proposer(text):
        return [ProposedClaim(text="Amina is a pirate.", quote="Amina sailed the seas.")]

    with pytest.raises(ValueError, match="not found"):
        ClaimExtractor(proposer).extract(make_scene(SENTENCE))
