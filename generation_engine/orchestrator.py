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
from .team_stubs import retrieve_canon, verify_scene


def run_pipeline(request: DemoRequest) -> PipelineResult:
    """Run the selected generation mode and return its results."""

    # Reject unsupported modes and invalid repair limits.
    if request.mode not in ("basic", "rag", "verified"):
        raise ValueError("Mode must be 'basic', 'rag', or 'verified'.")

    if (
        not isinstance(request.max_repair_attempts, int)
        or request.max_repair_attempts < 0
    ):
        raise ValueError("The repair limit must be a non-negative integer.")

    # Basic mode generates without canon.
    # RAG and verified modes retrieve a list of shared CanonFact objects.
    canon_facts = (
        []
        if request.mode == "basic"
        else retrieve_canon(request.prompt)
    )

    # Your generation function returns text.
    initial_text = generate_scene(request.prompt, canon_facts)

    # Wrap the text in a local Scene object to track revisions.
    initial_scene = Scene(
        scene_id="scene_001",
        text=initial_text,
        revision=0,
    )

    # Preserve the original scene while tracking the latest version.
    current_scene = initial_scene

    # Store the shared report returned by every verification call.
    reports: list[VerificationReport] = []

    # Count actual repair calls.
    repair_attempts = 0

    # Basic and RAG modes do not verify or repair their outputs.
    if request.mode in ("basic", "rag"):
        return PipelineResult(
            status="unverified",
            initial_scene=initial_scene,
            final_scene=current_scene,
            reports=reports,
            repair_attempts=repair_attempts,
        )

    # Verified mode checks the initial scene and every repaired version.
    while True:
        # Pass the scene text and the same retrieved canon to the verifier.
        # It already returns the shared VerificationReport object.
        report = verify_scene(
            current_scene.text,
            canon_facts,
        )

        reports.append(report)

        # An empty or uncertain report needs user review.
        # Zero detected contradictions alone does not establish success.
        if not report.claims or report.summary.uncertain > 0:
            return PipelineResult(
                status="needs_review",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # No contradictions or uncertainty remain in this report.
        # This does not automatically approve new facts for canon.
        if report.summary.contradictions == 0:
            return PipelineResult(
                status="verified",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # Check the limit AFTER verification so the final repair
        # always gets rechecked before the workflow stops.
        if repair_attempts >= request.max_repair_attempts:
            return PipelineResult(
                status="needs_review",
                initial_scene=initial_scene,
                final_scene=current_scene,
                reports=reports,
                repair_attempts=repair_attempts,
            )

        # Repair the conflicting content using the report and canon.
        repaired_text = repair_scene(
            current_scene.text,
            report,
            canon_facts,
        )

        # Count this repair exactly once.
        repair_attempts += 1

        # Create a new revision without overwriting the original scene.
        current_scene = Scene(
            scene_id=current_scene.scene_id,
            text=repaired_text,
            revision=current_scene.revision + 1,
        )

        # The loop now returns to verify_scene() to check this revision.