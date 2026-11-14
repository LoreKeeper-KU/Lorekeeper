# Authored by Saif Altamimi 11/14/2026

"""Internal helper models for the multimodal module (not shared with the team)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class FactCheck(BaseModel):
    """The vision model's verdict on ONE canon fact."""

    fact_id: str = Field(description="The id of the fact being checked, copied exactly")
    status: Literal["match", "mismatch", "unable_to_assess"]
    observed: Optional[str] = Field(
        default=None, description="What is actually visible, or null if not visible"
    )
    explanation: str = Field(description="One short sentence about what you saw")


class VisionCheckResult(BaseModel):
    """Everything the vision model returns: one FactCheck per fact."""

    checks: list[FactCheck]