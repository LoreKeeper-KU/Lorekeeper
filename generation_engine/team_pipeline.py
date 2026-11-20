# Authored by Abdullah on 18/11/2026
# Coordinates the team modules without changing their shared contracts.

from dataclasses import dataclass, field
from typing import Any, Callable

from shared.schemas import CanonFact, VisualAsset, VisualReport

from .models import DemoRequest, PipelineResult
from .orchestrator import run_pipeline


@dataclass
class TeamServices:
    # These hold the functions used by the workflow.
    # Tests can supply fake functions instead of making API calls.
    retrieve: Callable
    generate: Callable
    verify: Callable
    repair: Callable

    generate_visual: Callable | None = None
    check_visual: Callable | None = None
    build_visual_report: Callable | None = None
    repair_visual: Callable | None = None


@dataclass
class TeamResult:
    text: PipelineResult
    canon_facts: list[CanonFact]

    visual_status: str = "not_requested"
    asset: VisualAsset | None = None
    visual_report: VisualReport | None = None
    visual_checks: Any = None

    visual_repair_attempts: int = 0
    visual_review_reasons: list[str] = field(default_factory=list)
    visual_error: str | None = None


def coverage_issues(
    facts: list[CanonFact],
    result,
) -> list[str]:
    """Identify facts that were not clearly assessed in the image."""

    expected = {fact.id for fact in facts}
    seen: set[str] = set()
    reasons = []

    if not expected:
        reasons.append(
            "No canon facts were supplied for visual verification."
        )

    for check in result.checks:
        if check.fact_id not in expected:
            reasons.append(
                f"Unknown evidence ID: {check.fact_id}"
            )

        if check.fact_id in seen:
            reasons.append(
                f"Duplicate visual assessment: {check.fact_id}"
            )

        seen.add(check.fact_id)

        if check.status == "unable_to_assess":
            reasons.append(
                f"Unable to assess {check.fact_id}: "
                f"{check.explanation}"
            )

    for fact_id in sorted(expected - seen):
        reasons.append(
            f"Missing visual assessment: {fact_id}"
        )

    return reasons


def run_team_pipeline(
    request: DemoRequest,
    services: TeamServices,
    *,
    include_visuals: bool = False,
    max_visual_repairs: int = 1,
) -> TeamResult:
    """Run the verified text workflow and optionally create artwork."""

    if request.mode != "verified":
        raise ValueError(
            "The full-team demo requires verified mode."
        )

    if (
        type(request.max_repair_attempts) is not int
        or request.max_repair_attempts < 0
    ):
        raise ValueError(
            "The text repair limit must be a non-negative integer."
        )

    if (
        type(max_visual_repairs) is not int
        or max_visual_repairs < 0
    ):
        raise ValueError(
            "The visual repair limit must be a non-negative integer."
        )

    visual_services = (
        services.generate_visual,
        services.check_visual,
        services.build_visual_report,
        services.repair_visual,
    )

    if include_visuals and any(
        callback is None for callback in visual_services
    ):
        raise ValueError(
            "All visual services must be configured."
        )

    # Retrieve once and use the same facts throughout the run.
    # Generated content is never automatically added to accepted canon.
    facts = services.retrieve(request.prompt)

    if not facts:
        raise ValueError(
            "No approved canon was retrieved. Run --list-canon and use an "
            "existing entity name such as Amina, Khalid or Northern Kingdom. "
            "If the database is empty, ask the canon owner to add approved facts."
        )

    text_result = run_pipeline(
        request,
        retrieve=lambda _query: facts,
        generate=services.generate,
        verify=services.verify,
        repair=services.repair,
    )

    result = TeamResult(
        text=text_result,
        canon_facts=facts,
    )

    if not include_visuals:
        return result

    # Avoid making artwork from text with unresolved problems.
    if text_result.status != "verified":
        result.visual_status = "skipped_text_needs_review"
        return result

    try:
        result.asset = services.generate_visual(
            text_result.final_scene.text,
            facts,
        )

        # Raw checks preserve "unable_to_assess".
        result.visual_checks = services.check_visual(
            result.asset,
            facts,
        )

        result.visual_report = services.build_visual_report(
            result.asset,
            facts,
            result.visual_checks,
        )

        if (
            not result.visual_report.consistent
            and max_visual_repairs > 0
        ):
            repaired = services.repair_visual(
                result.asset,
                result.visual_report,
                facts,
                max_attempts=max_visual_repairs,
            )

            result.asset = repaired.asset
            result.visual_report = repaired.report
            result.visual_repair_attempts = repaired.attempts

            # Saif's repair loop checks mismatches after editing.
            # This final raw check also preserves uncertainty and coverage.
            result.visual_checks = services.check_visual(
                result.asset,
                facts,
            )

            result.visual_report = services.build_visual_report(
                result.asset,
                facts,
                result.visual_checks,
            )

        result.visual_review_reasons = coverage_issues(
            facts,
            result.visual_checks,
        )

        result.visual_review_reasons.extend(
            result.visual_report.issues
        )

        result.visual_status = (
            "no_mismatches_detected"
            if (
                result.visual_report.consistent
                and not result.visual_review_reasons
            )
            else "needs_review"
        )

    except Exception as exc:
        # Preserve the completed text result if the image stage fails.
        # Do not save raw provider responses that might contain secrets.
        result.visual_status = "error"

        result.visual_error = (
            f"Visual stage failed ({type(exc).__name__}). "
            "Check image-model access, configuration and provider availability."
        )

    return result