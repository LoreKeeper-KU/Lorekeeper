"""Smoke checks against the real NLI model. Run with: python -m pytest -m model"""

import pytest

from continuity_checker.canon_verifier import CanonVerifier, Verdict
from continuity_checker.claim_extractor import ClaimExtractor, ProposedClaim
from continuity_checker.contradiction_classifier import ContradictionClassifier
from continuity_checker.nli_comparator import NLIComparator
from continuity_checker.models import CanonFact, Claim, ClaimClassification, Scene, SourceSpan

pytestmark = pytest.mark.model

MODEL_NAME = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

F001 = CanonFact(
    id="F001", subject="char_amina", predicate="rules",
    object="Northern_Kingdom",
)
F002 = CanonFact(
    id="F002", subject="char_amina", predicate="magic_ability",
    object="none",
)


def claim(text):
    return Claim(claim_id="C001", text=text, source_span=SourceSpan(start=0, end=10))


@pytest.fixture(scope="module")
def nli():
    return NLIComparator.from_pretrained(MODEL_NAME)


def test_amina_firestorm_claim_contradicts_the_no_magic_fact(nli):
    assert nli(claim("Amina can summon magical firestorms."), F002) == Verdict.CONTRADICTION


def test_ruling_claim_is_entailed_by_the_rules_fact(nli):
    assert nli(claim("Amina rules the Northern Kingdom."), F001) == Verdict.ENTAILMENT


def test_unrelated_detail_is_neutral_to_the_magic_fact(nli):
    assert nli(claim("Amina carries a decorated shield."), F002) == Verdict.NEUTRAL


def test_whole_verifier_reports_the_amina_contradiction_with_the_real_model(nli):
    scene = Scene(
        scene_id="scene_001",
        world_id="world_001",
        text=(
            "Princess Amina raised her hands and summoned a magical firestorm "
            "to destroy the invading army."
        ),
    )
    proposals = [
        ProposedClaim(text="Amina can summon magical firestorms.", quote=scene.text)
    ]
    verifier = CanonVerifier(
        extractor=ClaimExtractor(lambda text: proposals),
        comparator=nli,
        classifier=ContradictionClassifier(),
    )

    report = verifier.verify_scene(scene, [F001, F002])

    assert report.summary.contradictions == 1
    (finding,) = report.claims
    assert finding.classification == ClaimClassification.CONTRADICTION
    assert finding.evidence_fact_ids == ["F002"]
