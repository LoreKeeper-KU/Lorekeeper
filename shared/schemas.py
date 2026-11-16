# Written by Abdulaziz Albastaki in October 2026
"""Shared Pydantic contracts for the LoreKeeper senior design project.

All teammates import these classes instead of creating their own dictionary
shapes. This file describes data; it does NOT implement retrieval, LLM calls,
contradiction detection, story repair, or image generation.

Current public function contracts (do not change without team agreement):

Abdulaziz:
    add_fact(fact: CanonFact) -> None
    retrieve_canon(query: str) -> list[CanonFact]

Faris:
    verify_scene(scene: str, canon_facts: list[CanonFact]) -> VerificationReport

Abdullah:
    generate_scene(prompt: str, canon_facts: list[CanonFact]) -> str
    repair_scene(scene: str, report: VerificationReport,
                 canon_facts: list[CanonFact]) -> str

Saif:
    generate_visual(scene: str, canon_facts: list[CanonFact]) -> VisualAsset
    verify_visual(asset: VisualAsset,
                  canon_facts: list[CanonFact]) -> VisualReport

Requires: pydantic >= 2.0
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class LoreKeeperModel(BaseModel):
    """Shared validation policy: reject unexpected fields/typing mistakes."""

    model_config = ConfigDict(extra="forbid")


class CanonFact(LoreKeeperModel):
    """An *accepted* fact in the fictional world (Abdulaziz's output).

    Example:
        CanonFact(
            id="fact-003",
            subject="Captain Arin's father",
            predicate="status",
            object="alive",
        )

    `id` is stable so other modules can reference the source of a decision.
    A fact is not necessarily exclusive: 'weapon=golden spear' does not prove
    Arin cannot also carry a silver sword.
    """

    id: str = Field(min_length=1, description="Stable unique ID in the canon store")
    subject: str = Field(min_length=1, description="Entity the fact concerns")
    predicate: str = Field(min_length=1, description="Relationship or attribute")
    object: str = Field(min_length=1, description="Value or target entity")


class ClaimClassification(str, Enum):
    """The project's four-way classification (Faris uses every category)."""

    SUPPORTED = "SUPPORTED"
    VALID_NEW_ADDITION = "VALID_NEW_ADDITION"
    CONTRADICTION = "CONTRADICTION"
    UNCERTAIN = "UNCERTAIN"


class ClaimAssessment(LoreKeeperModel):
    """Faris's evaluation of one atomic claim from the generated scene.

    Example:
        ClaimAssessment(
            claim="Arin's father died in the Great War.",
            classification=ClaimClassification.CONTRADICTION,
            reason="Canon says Arin's father is alive.",
            evidence_fact_ids=["fact-003"],
        )

    `evidence_fact_ids` must refer to CanonFact.id values in the supplied
    canon list. If no canon directly supports a claim, leave it empty.
    """

    claim: str = Field(min_length=1, description="One checkable statement")
    classification: ClaimClassification
    reason: str = Field(min_length=1, description="Short evidence-based rationale")
    evidence_fact_ids: list[str] = Field(
        default_factory=list,
        description="IDs of canon facts relevant to this decision",
    )


class VerificationSummary(LoreKeeperModel):
    """Counts of Faris's four classification categories."""

    supported: int = Field(ge=0)
    valid_new_additions: int = Field(ge=0)
    contradictions: int = Field(ge=0)
    uncertain: int = Field(ge=0)


class VerificationReport(LoreKeeperModel):
    """Faris's output; Abdullah's repair_scene() consumes this exact type.

    The summary is computed from claims to prevent inconsistent counts.
    Example serialization:
        {
          "claims": [{"claim": "...", "classification": "CONTRADICTION",
                      "reason": "...", "evidence_fact_ids": ["fact-003"]}],
          "summary": {"supported": 0, "valid_new_additions": 0,
                      "contradictions": 1, "uncertain": 0}
        }
    """

    claims: list[ClaimAssessment] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def ignore_derived_summary(cls, value: object) -> object:
        """Permit parsing serialized reports; never trust incoming counters."""
        if isinstance(value, dict) and "summary" in value:
            return {key: val for key, val in value.items() if key != "summary"}
        return value

    @computed_field
    @property
    def summary(self) -> VerificationSummary:
        categories = [assessment.classification for assessment in self.claims]
        return VerificationSummary(
            supported=categories.count(ClaimClassification.SUPPORTED),
            valid_new_additions=categories.count(ClaimClassification.VALID_NEW_ADDITION),
            contradictions=categories.count(ClaimClassification.CONTRADICTION),
            uncertain=categories.count(ClaimClassification.UNCERTAIN),
        )


class VisualAsset(LoreKeeperModel):
    """Saif's generated image plus the generation prompt.

    Example:
        VisualAsset(
            image_path="outputs/arin_palace.png",
            prompt="Captain Arin holds his golden spear at the palace.",
        )

    `image_path` is a local relative/absolute path for the starter design.
    The team may replace it with hosted storage later by agreement.
    """

    image_path: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class VisualReport(LoreKeeperModel):
    """Saif's consistency assessment of a generated visual.

    Example:
        VisualReport(
            image_path="outputs/arin_palace.png",
            consistent=False,
            issues=["Arin carries a blue staff, not his golden spear."],
            evidence_fact_ids=["fact-001"],
        )
    """

    image_path: str = Field(min_length=1)
    consistent: bool
    issues: list[str] = Field(default_factory=list)
    evidence_fact_ids: list[str] = Field(default_factory=list)
