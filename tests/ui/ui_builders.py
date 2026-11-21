# Authored by Faris
"""Builders shared by the UI tests: real pipeline result types with scripted content."""

from generation_engine.models import PipelineResult, Scene
from shared.schemas import ClaimAssessment, ClaimClassification, VerificationReport

ORIGINAL = "Princess Amina stood on the walls. She summoned a magical firestorm."
REPAIRED = "Princess Amina stood on the walls. She commanded her archers."


def assessment(claim, classification, reason, evidence=()):
    return ClaimAssessment(
        claim=claim,
        classification=classification,
        reason=reason,
        evidence_fact_ids=list(evidence),
    )


CONTRADICTION = assessment(
    "Amina summons a magical firestorm.",
    ClaimClassification.CONTRADICTION,
    "Canon states that Amina has no magical ability.",
    ["fact-001"],
)
OTHER_CONTRADICTION = assessment(
    "Amina flies over the castle.",
    ClaimClassification.CONTRADICTION,
    "Canon states that Amina cannot fly.",
    ["fact-002"],
)
SUPPORTED = assessment(
    "Amina commands archers.",
    ClaimClassification.SUPPORTED,
    "Canon establishes that Amina commands archers.",
    ["fact-003", "fact-004"],
)
NEW_ADDITION = assessment(
    "The wall is made of white stone.",
    ClaimClassification.VALID_NEW_ADDITION,
    "Nothing in canon rules this out.",
)
UNCERTAIN = assessment(
    "The attackers came from the sea.",
    ClaimClassification.UNCERTAIN,
    "Canon neither supports nor contradicts this.",
)


def result(reports, status="verified", repairs=1, final=REPAIRED):
    """A PipelineResult whose reports hold the given lists of ClaimAssessments."""
    return PipelineResult(
        status=status,
        initial_scene=Scene(scene_id="scene_001", text=ORIGINAL, revision=0),
        final_scene=Scene(scene_id="scene_001", text=final, revision=repairs),
        reports=[VerificationReport(claims=claims) for claims in reports],
        repair_attempts=repairs,
    )


class FakePipeline:
    """Stands in for run_pipeline and records the requests it receives."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome
