# Authored by Abdullah on 31/10/2026
# This file controls the complete LoreKeeper workflow.
#
# Workflow:
# 1. Retrieve approved canon.
# 2. Generate a scene.
# 3. Check the scene for contradictions.
# 4. Repair the scene if needed.
# 5. Check the repaired scene again.
# 6. Stop when the scene passes or the repair limit is reached.


from shared.schemas import VerificationReport

from .models import DemoRequest, PipelineResult, Scene
from .story_generator import generate_scene, repair_scene

from .team_stubs import retrieve_canon
from continuity_checker.checker import verify_scene


def run_pipeline(
    request: DemoRequest,
    *,
    retrieve=None,
    generate=None,
    verify=None,
    repair=None,
) -> PipelineResult:
    """Run the selected generation mode and return its results."""

    # The team demo supplies real functions here.
    # Existing demo callers can continue using their original functions.
    retrieve = retrieve if retrieve is not None else retrieve_canon
    generate = generate if generate is not None else generate_scene
    verify = verify if verify is not None else verify_scene
    repair = repair if repair is not None else repair_scene

    if request.mode not in ("basic", "rag", "verified"):
        raise ValueError("Mode must be 'basic', 'rag', or 'verified'.")

    if (
        type(request.max_repair_attempts) is not int
        or request.max_repair_attempts < 0
    ):
        raise ValueError("The repair limit must be a non-negative integer.")

    # Basic mode generates without retrieving canon.
    canon_facts = (
        []
        if request.mode == "basic"
        else retrieve(request.prompt)
    )

    initial_text = generate(request.prompt, canon_facts)

    initial_scene = Scene(
        scene_id="scene_001",
        text=initial_text,
        revision=0,
    )

    # Preserve the initial scene while tracking later revisions.
    current_scene = initial_scene
    reports: list[VerificationReport] = []
    repair_attempts = 0

    # Basic and RAG modes do not verify or repair.
    if request.mode in ("basic", "rag"):
        return PipelineResult(
            status="unverified",
            initial_scene=initial_scene,
            final_scene=current_scene,
            reports=reports,
            repair_attempts=repair_attempts,
        )

    while True:
        # Check the current scene against the same retrieved facts.
        report = verify(
            current_scene.text,
            canon_facts,
        )

        reports.append(report)

        # An empty report cannot establish consistency.
        if not report.claims:
            return PipelineResult(
                status="needs_review",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # If no contradictions remain, uncertainty determines whether
        # the result still needs human review.
        if report.summary.contradictions == 0:
            return PipelineResult(
                status=(
                    "needs_review"
                    if report.summary.uncertain > 0
                    else "verified"
                ),
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # Check the limit after verification, so the last allowed
        # repair always gets checked.
        if repair_attempts >= request.max_repair_attempts:
            return PipelineResult(
                status="needs_review",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # Repair confirmed contradictions, even if other claims
        # in the report remain uncertain.
        repaired_text = repair(
            current_scene.text,
            report,
            canon_facts,
        )

        repair_attempts += 1

        # Stop if the repair function made no change.
        if repaired_text == current_scene.text:
            return PipelineResult(
                status="needs_review",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        current_scene = Scene(
            scene_id=current_scene.scene_id,
            text=repaired_text,
            revision=current_scene.revision + 1,
        )

        # The loop checks this new revision next.