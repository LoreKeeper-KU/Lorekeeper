# Authored by Faris
"""How a PipelineResult is summarised for display.

Pure functions over the existing result types: no Streamlit, no generation, retrieval or
verification logic. Everything here only reads what run_pipeline() already returned.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from generation_engine.models import PipelineResult
from shared.schemas import ClaimAssessment, ClaimClassification


@dataclass(frozen=True)
class CanonCheck:
    headline: str  # e.g. "Verified" or "1 contradiction detected and repaired"
    tone: str  # "verified", "review", "skipped" or "error"; the UI picks colours from it
    repaired: bool  # the final scene differs from the original generation


@dataclass(frozen=True)
class Step:
    label: str
    state: str  # "done", "alert" or "review"


def _count(number: int, singular: str, plural: str) -> str:
    return f"{number} {singular if number == 1 else plural}"


def was_repaired(result: PipelineResult) -> bool:
    return result.final_scene.text != result.initial_scene.text


def canon_check(result: PipelineResult) -> CanonCheck:
    repaired = was_repaired(result)
    if result.status == "error":
        return CanonCheck("Verification could not complete", "error", repaired)
    if not result.reports:
        return CanonCheck("Not run in this mode", "skipped", repaired)

    # Contradictions found in the original generation, before any repair.
    found = result.reports[0].summary.contradictions
    last = result.reports[-1].summary

    if result.status == "verified":
        if repaired and found:
            headline = f"{_count(found, 'contradiction', 'contradictions')} detected and repaired"
        else:
            headline = "Verified"
        return CanonCheck(headline, "verified", repaired)

    if result.status == "needs_review":
        if last.contradictions:
            headline = f"{_count(last.contradictions, 'contradiction', 'contradictions')}"
            headline += " remains" if last.contradictions == 1 else " remain"
            if result.repair_attempts:
                headline += (
                    f" after {_count(result.repair_attempts, 'repair attempt', 'repair attempts')}"
                )
            headline += " — needs review"
        elif last.uncertain:
            prefix = (
                f"{_count(found, 'contradiction', 'contradictions')} repaired · "
                if repaired and found
                else ""
            )
            verb = "needs" if last.uncertain == 1 else "need"
            headline = f"{prefix}{_count(last.uncertain, 'uncertain claim', 'uncertain claims')} {verb} review"
        elif not result.reports[-1].claims:
            headline = "No checkable claims were found — needs review"
        else:
            headline = "Needs review"
        return CanonCheck(headline, "review", repaired)

    return CanonCheck(f"Status: {result.status}", "review", repaired)


def repair_steps(result: PipelineResult) -> list:
    """The progression from the original generation to the final outcome.

    Empty unless the canon check found a contradiction, so clean scenes stay compact.
    """
    if result.status == "error" or not result.reports:
        return []
    found = result.reports[0].summary.contradictions
    if not found:
        return []

    steps = [
        Step("Original generation", "done"),
        Step(f"Canon check found {_count(found, 'contradiction', 'contradictions')}", "alert"),
    ]
    attempts = result.repair_attempts
    if attempts:
        if not was_repaired(result):
            steps.append(Step("Repair attempted (no change)", "alert"))
        elif attempts == 1:
            steps.append(Step("Repair performed", "done"))
        else:
            steps.append(Step(f"Repair performed ({attempts} attempts)", "done"))
        if len(result.reports) > 1:
            steps.append(Step("Rechecked", "done"))
    steps.append(
        Step("Canon verified", "done")
        if result.status == "verified"
        else Step("Needs review", "review")
    )
    return steps


def claim_repair_state(
    result: PipelineResult, pass_index: int, assessment: ClaimAssessment
) -> Optional[str]:
    """For a contradiction: "repaired" if a later pass no longer reports it, else "unresolved"."""
    if assessment.classification != ClaimClassification.CONTRADICTION:
        return None
    for report in result.reports[pass_index + 1 :]:
        for later in report.claims:
            if (
                later.claim == assessment.claim
                and later.classification == ClaimClassification.CONTRADICTION
            ):
                return "unresolved"
    return "repaired" if pass_index < len(result.reports) - 1 else "unresolved"


def find_image(result: PipelineResult) -> Optional[str]:
    """The artwork for this result, once the pipeline provides one.

    PipelineResult has no image yet; this reads an optional `image_path` (the same name
    VisualAsset uses). A missing, empty or non-existent file counts as no image, so the
    page never shows a broken picture.
    """
    path = getattr(result, "image_path", None)
    if not isinstance(path, str) or not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return path if Path(path).is_file() else None


def classification_label(value: str) -> str:
    return value.replace("_", " ")


def classification_slug(value: str) -> str:
    return value.lower().replace("_", "-")


def session_title(prompt: str, limit: int = 40) -> str:
    """A short single-line title for the sidebar's list of scenes."""
    text = " ".join(prompt.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
