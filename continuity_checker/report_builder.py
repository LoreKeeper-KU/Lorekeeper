"""Convert internal VerifiedClaims into the team's public VerificationReport.

The team report has no field for claim IDs, source spans or suggested actions, so they
are dropped here (the suggested action is folded into the reason).
"""

from continuity_checker.models import ClaimAssessment, VerificationReport, VerifiedClaim


def build_assessment(claim: VerifiedClaim) -> ClaimAssessment:
    reason = claim.explanation
    if claim.suggested_action:
        reason = f"{reason} Suggested action: {claim.suggested_action}"
    return ClaimAssessment(
        claim=claim.text,
        classification=claim.classification,
        reason=reason,
        evidence_fact_ids=claim.evidence_ids,
    )


def build_report(verified_claims: list[VerifiedClaim]) -> VerificationReport:
    return VerificationReport(claims=[build_assessment(c) for c in verified_claims])
