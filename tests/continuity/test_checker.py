# Authored by Faris
import typing

import pytest

from continuity_checker import checker
from continuity_checker.canon_verifier import CanonVerifier, Verdict
from continuity_checker.checker import (
    VerifierNotConfiguredError,
    configure_verifier,
    verify_scene,
)
from continuity_checker.claim_extractor import ClaimExtractor, ProposedClaim
from continuity_checker.contradiction_classifier import ContradictionClassifier
from shared.schemas import CanonFact, ClaimClassification, VerificationReport

SCENE = (
    "Captain Arin entered the royal palace in Eldoria. "
    "The queen greeted him warmly. "
    "Arin remembered that his father had died in the Great War."
)
FACTS = [
    CanonFact(id="fact-001", subject="Captain Arin", predicate="weapon", object="golden spear"),
    CanonFact(id="fact-002", subject="Queen Lyra", predicate="rules", object="Eldoria"),
    CanonFact(
        id="fact-003", subject="Captain Arin's father", predicate="status", object="alive"
    ),
]
FATHER = "Arin's father died in the Great War."
GREETING = "Queen Lyra greeted Arin warmly."


@pytest.fixture(autouse=True)
def reset_configuration():
    configure_verifier(None)
    yield
    configure_verifier(None)


def fake_verifier(seen_texts=None):
    proposals = [
        ProposedClaim(text=FATHER, quote="Arin remembered that his father had died in the Great War."),
        ProposedClaim(text=GREETING, quote="The queen greeted him warmly."),
    ]

    def proposer(text):
        if seen_texts is not None:
            seen_texts.append(text)
        return proposals

    def comparator(claim, fact):
        if (claim.text, fact.id) == (FATHER, "fact-003"):
            return Verdict.CONTRADICTION
        return Verdict.NEUTRAL

    return CanonVerifier(
        extractor=ClaimExtractor(proposer),
        comparator=comparator,
        classifier=ContradictionClassifier(lambda claim, evidence: "greeted" in claim.text),
    )


def test_public_signature_matches_the_team_contract_exactly():
    hints = typing.get_type_hints(checker.verify_scene)
    assert list(hints) == ["scene", "canon_facts", "return"]
    assert hints["scene"] is str
    assert hints["canon_facts"] == list[CanonFact]
    assert hints["return"] is VerificationReport


def test_without_a_configured_verifier_it_raises_a_clear_configuration_error():
    with pytest.raises(VerifierNotConfiguredError, match="configure_verifier"):
        verify_scene(SCENE, FACTS)


def test_the_configuration_error_is_a_runtime_error_not_a_missing_implementation():
    assert issubclass(VerifierNotConfiguredError, RuntimeError)
    assert not issubclass(VerifierNotConfiguredError, NotImplementedError)


def test_a_configured_verifier_receives_the_scene_text_and_returns_the_team_report():
    seen = []
    configure_verifier(fake_verifier(seen))

    report = verify_scene(SCENE, FACTS)

    assert seen == [SCENE]
    assert isinstance(report, VerificationReport)
    by_claim = {a.claim: a for a in report.claims}
    assert by_claim[FATHER].classification == ClaimClassification.CONTRADICTION
    assert by_claim[FATHER].evidence_fact_ids == ["fact-003"]
    assert by_claim[GREETING].classification == ClaimClassification.VALID_NEW_ADDITION
    assert report.summary.contradictions == 1
    assert report.summary.valid_new_additions == 1


def test_cited_evidence_ids_exist_in_the_supplied_canon():
    configure_verifier(fake_verifier())

    report = verify_scene(SCENE, FACTS)

    supplied = {fact.id for fact in FACTS}
    cited = {i for assessment in report.claims for i in assessment.evidence_fact_ids}
    assert cited <= supplied


def test_reconfiguring_replaces_the_previous_verifier():
    configure_verifier(fake_verifier())
    configure_verifier(None)
    with pytest.raises(VerifierNotConfiguredError):
        verify_scene(SCENE, FACTS)
