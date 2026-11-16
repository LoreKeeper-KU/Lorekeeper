# Authored by Faris
from continuity_checker.models import (
    ClaimClassification,
    SourceSpan,
    VerificationReport,
    VerifiedClaim,
)
from continuity_checker.report_builder import build_report


def verified(claim_id, classification, evidence_ids=(), suggested_action=None):
    return VerifiedClaim(
        claim_id=claim_id,
        text=f"claim {claim_id}",
        source_span=SourceSpan(start=3, end=9),
        classification=classification,
        evidence_ids=list(evidence_ids),
        explanation=f"because {claim_id}",
        suggested_action=suggested_action,
    )


def test_each_verified_claim_becomes_one_assessment_with_mapped_fields():
    report = build_report(
        [verified("C001", ClaimClassification.CONTRADICTION, ["fact-003"])]
    )

    (assessment,) = report.claims
    assert assessment.claim == "claim C001"
    assert assessment.classification == ClaimClassification.CONTRADICTION
    assert assessment.evidence_fact_ids == ["fact-003"]
    assert assessment.reason == "because C001"


def test_the_suggested_action_is_appended_to_the_reason_when_present():
    report = build_report(
        [
            verified("C001", ClaimClassification.CONTRADICTION, ["f1"], "Revise it."),
            verified("C002", ClaimClassification.UNCERTAIN),
        ]
    )

    assert report.claims[0].reason == "because C001 Suggested action: Revise it."
    assert report.claims[1].reason == "because C002"


def test_team_summary_counts_every_category():
    report = build_report(
        [
            verified("C001", ClaimClassification.SUPPORTED, ["f1"]),
            verified("C002", ClaimClassification.VALID_NEW_ADDITION),
            verified("C003", ClaimClassification.CONTRADICTION, ["f2"]),
            verified("C004", ClaimClassification.CONTRADICTION, ["f3"]),
            verified("C005", ClaimClassification.UNCERTAIN),
        ]
    )

    assert report.summary.model_dump() == {
        "supported": 1,
        "valid_new_additions": 1,
        "contradictions": 2,
        "uncertain": 1,
    }


def test_no_claims_gives_an_empty_report():
    report = build_report([])
    assert report.claims == []
    assert report.summary.contradictions == 0


def test_public_report_is_the_team_type_and_hides_internal_ids_and_spans():
    report = build_report([verified("C001", ClaimClassification.UNCERTAIN)])

    assert isinstance(report, VerificationReport)
    data = report.model_dump(mode="json")
    assert set(data["claims"][0]) == {"claim", "classification", "reason", "evidence_fact_ids"}
    assert VerificationReport.model_validate(data) == report
