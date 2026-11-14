"""Internal helper models for the multimodal module (not shared with the team)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from shared.schemas import VisualAsset, VisualReport


class FactCheck(BaseModel):
    """The vision model's verdict on ONE canon fact."""

    fact_id: str = Field(description="The id of the fact being checked, copied exactly")
    status: Literal["match", "mismatch", "unable_to_assess"]
    observed: Optional[str] = Field(
        default=None,
        description="Only the visible value in 1-3 words (e.g. 'gold'), or null if not visible",
    )
    explanation: str = Field(description="One short sentence about what you saw")


class VisionCheckResult(BaseModel):
    """Everything the vision model returns: one FactCheck per fact."""

    checks: list[FactCheck]


class VisualRepairResult(BaseModel):
    """What repair_visual returns: the final image, its report, and how it went."""

    asset: VisualAsset  # the final image (original if no repair was needed)
    report: VisualReport  # the check of that final image
    attempts: int  # how many edits were made (0 = none needed)
    needs_human_review: bool  # True if mismatches remain after all attempts
