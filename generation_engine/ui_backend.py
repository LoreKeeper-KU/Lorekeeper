# Authored by Abdullah on 21/11/2026
# Connects the web interface to the real team modules.

from functools import partial

from .ai_story_generator import AIStoryGenerator
from .orchestrator import run_pipeline
from .team_pipeline import (
    TeamResult,
    TeamServices,
    run_team_pipeline,
)


class NoCanonError(ValueError):
    """The prompt did not retrieve accepted world facts."""


def retrieve_for_request(request):
    # Basic mode does not use canon.
    if request.mode == "basic":
        return []

    from canon_memory.memory import retrieve_canon

    facts = retrieve_canon(request.prompt)

    if not facts:
        raise NoCanonError(
            "No approved facts matched this request. "
            "Include Amina or Northern Kingdom in your prompt. "
            "If the database is empty, load the demo canon first."
        )

    return facts


def run_ui_request(
    request,
    canon_facts,
    client,
    *,
    comparator=None,
    include_visuals=False,
    max_visual_repairs=1,
):
    """Return a TeamResult in all three sidebar modes."""

    if request.mode not in ("basic", "rag", "verified"):
        raise ValueError("Unknown pipeline mode.")

    if request.mode != "basic" and not canon_facts:
        raise NoCanonError(
            "No approved canon was supplied for this request."
        )

    facts = [] if request.mode == "basic" else canon_facts
    story = AIStoryGenerator(client)

    # These modes generate real text without running verification.
    if request.mode in ("basic", "rag"):
        text = run_pipeline(
            request,
            retrieve=lambda _query: facts,
            generate=story.generate_scene,
            repair=story.repair_scene,
        )

        return TeamResult(
            text=text,
            canon_facts=facts,
            visual_status="not_requested",
        )

    if comparator is None:
        raise ValueError(
            "Verified mode needs the continuity model."
        )

    from continuity_checker.addition_judge import (
        LLMAdditionJudge,
    )
    from continuity_checker.canon_verifier import (
        CanonVerifier,
    )
    from continuity_checker.claim_extractor import (
        ClaimExtractor,
        SharedClientClaimProposer,
    )
    from continuity_checker.contradiction_classifier import (
        ContradictionClassifier,
    )
    from continuity_checker.models import Scene as CheckerScene

    # Each web request gets its own verifier.
    # This avoids sharing configure_verifier's global variable
    # between different browser sessions.
    verifier = CanonVerifier(
        extractor=ClaimExtractor(
            SharedClientClaimProposer(client)
        ),
        comparator=comparator,
        classifier=ContradictionClassifier(
            addition_judge=LLMAdditionJudge(client)
        ),
    )

    def verify(text, supplied_facts):
        return verifier.verify_scene(
            CheckerScene(
                scene_id="scene",
                world_id="world_001",
                text=text,
            ),
            supplied_facts,
        )

    services = TeamServices(
        retrieve=lambda _query: facts,
        generate=story.generate_scene,
        verify=verify,
        repair=story.repair_scene,
    )

    if include_visuals:
        from multimodal.visuals import (
            generate_visual,
            check_visual_facts,
            build_visual_report,
            repair_visual,
        )

        services.generate_visual = partial(
            generate_visual,
            ai=client,
        )

        services.check_visual = partial(
            check_visual_facts,
            ai=client,
        )

        services.build_visual_report = build_visual_report

        services.repair_visual = partial(
            repair_visual,
            ai=client,
        )

    return run_team_pipeline(
        request,
        services,
        include_visuals=include_visuals,
        max_visual_repairs=max_visual_repairs,
    )