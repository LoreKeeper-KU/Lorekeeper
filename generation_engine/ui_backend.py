# Authored by Abdullah on 21/11/2026
# Routes requests to character creation or scene generation.

from functools import partial
from typing import Literal

from .ai_story_generator import AIStoryGenerator
from .character_creator import CharacterDraft, create_character
from .orchestrator import run_pipeline
from .team_pipeline import TeamResult, TeamServices, run_team_pipeline


class NoCanonError(ValueError):
    """The scene request has no approved canon."""


Action = Literal["generate_scene", "create_character"]


def _validate_request(request, action):
    """Check the action, scene mode and prompt before making API calls."""

    if action not in ("generate_scene", "create_character"):
        raise ValueError("Choose generate_scene or create_character.")

    if request.mode not in ("basic", "rag", "verified"):
        raise ValueError("Unknown pipeline mode.")

    if not isinstance(request.prompt, str) or not request.prompt.strip():
        raise ValueError("Enter a non-empty prompt.")


def retrieve_for_request(
    request,
    *,
    action: Action = "generate_scene",
):
    """Retrieve approved context. Character creation allows empty canon."""

    _validate_request(request, action)

    # Basic scene generation does not use canon.
    if action == "generate_scene" and request.mode == "basic":
        return []

    from canon_memory.memory import retrieve_canon

    facts = retrieve_canon(request.prompt)

    # A new character can be created before any canon exists.
    # RAG and Verified scenes still need approved facts.
    if not facts and action == "generate_scene":
        raise NoCanonError(
            "No approved facts matched this scene request. "
            "Create a character and have its facts approved first, "
            "or use a character already in canon."
        )

    return facts


def run_ui_request(
    request,
    canon_facts,
    client,
    *,
    action: Action = "generate_scene",
    comparator=None,
    include_visuals=False,
    max_visual_repairs=1,
) -> TeamResult | CharacterDraft:
    """Return a character draft or run the existing scene workflow."""

    _validate_request(request, action)

    # Character creation is separate from the three scene modes.
    # It needs no existing canon, continuity model or image generation.
    if action == "create_character":
        return create_character(
            request.prompt,
            canon_facts,
            client,
        )

    # The remaining code handles scene generation.
    if request.mode != "basic" and not canon_facts:
        raise NoCanonError(
            "No approved canon was supplied for this scene request."
        )

    # Basic scenes ignore canon, even if the caller supplied some.
    facts = [] if request.mode == "basic" else canon_facts
    story = AIStoryGenerator(client)

    # Basic and RAG modes generate without verification.
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

    # Verified scenes require Faris's continuity model.
    if comparator is None:
        raise ValueError(
            "Verified mode needs the continuity model."
        )

    from continuity_checker.addition_judge import LLMAdditionJudge
    from continuity_checker.canon_verifier import CanonVerifier
    from continuity_checker.claim_extractor import (
        ClaimExtractor,
        SharedClientClaimProposer,
    )
    from continuity_checker.contradiction_classifier import (
        ContradictionClassifier,
    )
    from continuity_checker.models import Scene as CheckerScene

    # Keep the verifier local to this request.
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

    # Connect Saif's visual functions only when requested.
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