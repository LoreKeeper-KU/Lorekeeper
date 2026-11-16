# Authored by Faris
"""Internal models for the continuity checker, plus the team contracts it uses.

Scene, SourceSpan, Claim and VerifiedClaim exist only inside this module: they carry
claim IDs and source positions that the shared report cannot hold. The public result
is converted to the team's VerificationReport (see report_builder.py).
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from shared.schemas import (
    CanonFact,
    ClaimAssessment,
    ClaimClassification,
    VerificationReport,
)


class Scene(BaseModel):
    scene_id: str
    world_id: str
    text: str


class SourceSpan(BaseModel):
    """Character range in Scene.text; end is exclusive, like a Python slice."""

    start: int = Field(ge=0)
    end: int

    @model_validator(mode="after")
    def end_must_follow_start(self):
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class Claim(BaseModel):
    """A claim as extracted from a scene, before any verdict."""

    claim_id: str
    text: str
    source_span: SourceSpan


class VerifiedClaim(Claim):
    classification: ClaimClassification
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    suggested_action: Optional[str] = None

    @model_validator(mode="after")
    def findings_must_cite_evidence(self):
        needs_evidence = {ClaimClassification.SUPPORTED, ClaimClassification.CONTRADICTION}
        if self.classification in needs_evidence and not self.evidence_ids:
            raise ValueError(f"{self.classification.value} claims must cite evidence_ids")
        return self


__all__ = [
    "CanonFact",
    "Claim",
    "ClaimAssessment",
    "ClaimClassification",
    "Scene",
    "SourceSpan",
    "VerificationReport",
    "VerifiedClaim",
]
