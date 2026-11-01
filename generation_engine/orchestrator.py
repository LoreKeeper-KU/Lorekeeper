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


from .models import (
    DemoRequest,
    PipelineResult,
    Scene,
    VerificationReport,
)

from .story_generator import generate_story, repair_story
from .team_stubs import retrieve_canon, verify_scene


def run_pipeline(request: DemoRequest) -> PipelineResult:
    """
    Runs the LoreKeeper generation and repair workflow.
    """

    # Get the approved facts from the temporary canon function.
    canon = retrieve_canon()

    # Generate the first scene.
    initial_scene = generate_story(request)

    # Keep track of the current version of the scene.
    current_scene = initial_scene

    # Store every verification report.
    reports = []

    # Count how many repairs have been attempted.
    repair_attempts = 0

    # Basic mode only generates content.
    if request.mode == "basic":
        return PipelineResult(
            status="unverified",
            initial_scene=initial_scene,
            final_scene=current_scene,
            reports=[],
            repair_attempts=0,
        )

    # Check the scene and repeat if a repair is needed.
    while True:
        # The temporary verifier checks the scene text.
        verification = verify_scene(current_scene.text)

        # Convert the verifier dictionary into our data model.
        report = VerificationReport(
            scene_id=current_scene.scene_id,
            status=verification["status"],
            conflict=verification["conflict"],
            correction=verification["correction"],
        )

        # Save the report.
        reports.append(report)

        # If the scene is consistent, the workflow is complete.
        if report.status == "consistent":
            return PipelineResult(
                status="verified",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # If the repair limit is reached, send the result for user review.
        if repair_attempts >= request.max_repair_attempts:
            return PipelineResult(
                status="needs_review",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # Repair only the affected scene.
        current_scene = repair_story(current_scene, report)

        # Increase the repair count.
        repair_attempts += 1