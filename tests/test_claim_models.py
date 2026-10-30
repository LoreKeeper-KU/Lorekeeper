import pytest
from pydantic import ValidationError

from continuity_checker.models import (
    Claim,
    ClaimClassification,
    Scene,
    SourceSpan,
    VerifiedClaim,
)


def make_verified(**overrides):
    fields = dict(
        claim_id="C001",
        text="Amina can summon magical firestorms.",
        source_span=SourceSpan(start=0, end=40),
        classification=ClaimClassification.CONTRADICTION,
        evidence_ids=["F002"],
        explanation="Canon states Amina has no magical abilities.",
        suggested_action="Use a non-magical defensive action.",
    )
    fields.update(overrides)
    return VerifiedClaim(**fields)


def test_extracted_claim_needs_no_classification():
    claim = Claim(
        claim_id="C001",
        text="Amina can summon magical firestorms.",
        source_span=SourceSpan(start=0, end=40),
    )
    assert claim.source_span.end == 40


def test_verified_claim_matches_brief_example_json():
    data = make_verified().model_dump(mode="json")
    assert data["classification"] == "CONTRADICTION"
    assert data["evidence_ids"] == ["F002"]
    assert data["claim_id"] == "C001"


@pytest.mark.parametrize(
    "classification", [ClaimClassification.CONTRADICTION, ClaimClassification.SUPPORTED]
)
def test_supported_and_contradiction_must_cite_evidence(classification):
    with pytest.raises(ValidationError):
        make_verified(classification=classification, evidence_ids=[])


@pytest.mark.parametrize(
    "classification", [ClaimClassification.UNCERTAIN, ClaimClassification.VALID_NEW_ADDITION]
)
def test_uncertain_and_new_addition_may_have_no_evidence(classification):
    claim = make_verified(classification=classification, evidence_ids=[])
    assert claim.evidence_ids == []


def test_explanation_is_required_and_non_empty():
    with pytest.raises(ValidationError):
        make_verified(explanation="")


def test_suggested_action_is_optional():
    claim = make_verified(suggested_action=None)
    assert claim.suggested_action is None


def test_scene_requires_id_world_and_text():
    scene = Scene(scene_id="scene_001", world_id="world_001", text="Amina rules.")
    assert scene.text == "Amina rules."

    with pytest.raises(ValidationError):
        Scene(scene_id="scene_001", world_id="world_001")


def test_source_span_slices_the_scene_text():
    text = "Amina smiled. Amina summoned fire."
    span = SourceSpan(start=14, end=34)
    assert text[span.start : span.end] == "Amina summoned fire."


def test_source_span_rejects_empty_or_negative_ranges():
    with pytest.raises(ValidationError):
        SourceSpan(start=5, end=5)
    with pytest.raises(ValidationError):
        SourceSpan(start=-1, end=3)
