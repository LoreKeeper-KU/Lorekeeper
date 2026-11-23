# Authored by Abdullah on 18/11/2026
# Runs the complete team demo from the terminal.

import argparse
import json
import os

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _serialize(result) -> dict:
    """Convert the result into data that can be saved as JSON."""

    return {
        "text_status": result.text.status,
        "initial_scene": vars(result.text.initial_scene),
        "final_scene": vars(result.text.final_scene),
        "text_repair_calls": result.text.repair_attempts,

        "canon_snapshot": [
            fact.model_dump(mode="json")
            for fact in result.canon_facts
        ],

        "text_reports": [
            report.model_dump(mode="json")
            for report in result.text.reports
        ],

        "visual_status": result.visual_status,

        "visual_asset": (
            result.asset.model_dump(mode="json")
            if result.asset
            else None
        ),

        "visual_report": (
            result.visual_report.model_dump(mode="json")
            if result.visual_report
            else None
        ),

        "visual_checks": (
            result.visual_checks.model_dump(mode="json")
            if result.visual_checks
            else None
        ),

        "visual_repair_attempts": result.visual_repair_attempts,
        "visual_review_reasons": result.visual_review_reasons,
        "visual_error": result.visual_error,
    }


def main():
    parser = argparse.ArgumentParser(
        description="LoreKeeper full-team CLI demo"
    )

    parser.add_argument(
        "--prompt",
        default=(
            "Write a short scene about Amina in the Northern Kingdom."
        ),
    )

    parser.add_argument(
        "--list-canon",
        action="store_true",
        help="Show approved canon and exit without AI calls.",
    )

    parser.add_argument(
        "--visuals",
        action="store_true",
        help=(
            "Generate and check artwork after text passes; uses paid APIs."
        ),
    )

    parser.add_argument(
        "--max-text-repairs",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--max-visual-repairs",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    if args.max_text_repairs < 0 or args.max_visual_repairs < 0:
        parser.error("Repair limits must be non-negative.")

    # Make database and output paths relative to the Lorekeeper root.
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)

    # Load settings before importing the shared AI client.
    from dotenv import load_dotenv

    load_dotenv(root / ".env")

    from canon_memory.memory import (
        DEFAULT_WORLD_ID,
        retrieve_canon,
    )
    from canon_memory.canon_store import CanonStore

    # This option checks the database without making AI calls.
    if args.list_canon:
        facts = CanonStore().get_facts_by_world(
            DEFAULT_WORLD_ID
        )

        print(
            f"Approved facts in {DEFAULT_WORLD_ID}: {len(facts)}"
        )

        for fact in facts:
            print(
                f"{fact.id}: {fact.subject} | "
                f"{fact.predicate} | {fact.object}"
            )

        return

    # Retrieve before loading the NLI model or making API calls.
    facts = retrieve_canon(args.prompt)

    if not facts:
        parser.error(
            "No approved facts matched this prompt. Run --list-canon. "
            "Current aliases recognize Amina, Khalid and Northern Kingdom. "
            "Ask the canon owner to supply accepted facts if the database "
            "is empty."
        )

    print(
        f"Retrieved {len(facts)} approved facts:",
        flush=True,
    )

    for fact in facts:
        print(
            f"  {fact.id}: {fact.subject} | "
            f"{fact.predicate} | {fact.object}"
        )

    from shared.ai_client import AIClient

    from continuity_checker.addition_judge import (
        LLMAdditionJudge,
    )
    from continuity_checker.canon_verifier import (
        CanonVerifier,
    )
    from continuity_checker.checker import (
        configure_verifier,
        verify_scene,
    )
    from continuity_checker.claim_extractor import (
        ClaimExtractor,
        SharedClientClaimProposer,
    )
    from continuity_checker.contradiction_classifier import (
        ContradictionClassifier,
    )
    from continuity_checker.nli_comparator import (
        NLIComparator,
    )

    from .ai_story_generator import AIStoryGenerator
    from .models import DemoRequest
    from .team_pipeline import (
        TeamServices,
        run_team_pipeline,
    )

    # Share one client between text generation, checking and visuals.
    client = AIClient()
    story = AIStoryGenerator(client)

    print("Loading the continuity model...", flush=True)

    verifier = CanonVerifier(
        extractor=ClaimExtractor(
            SharedClientClaimProposer(client)
        ),
        comparator=NLIComparator.from_pretrained(
            "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
        ),
        classifier=ContradictionClassifier(
            addition_judge=LLMAdditionJudge(client)
        ),
    )

    # Abdulaziz's real retrieval already ran above.
    # Reuse its exact results throughout this run.
    services = TeamServices(
        retrieve=lambda _query: facts,
        generate=story.generate_scene,
        verify=verify_scene,
        repair=story.repair_scene,
    )

    if args.visuals:
        from functools import partial

        from multimodal.visuals import (
            generate_visual,
            check_visual_facts,
            build_visual_report,
            repair_visual,
        )

        # partial supplies the shared client automatically.
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

    configure_verifier(verifier)

    print(
        "Generating, verifying and repairing text...",
        flush=True,
    )

    if args.visuals:
        print(
            "Artwork will run only if the text passes. "
            "Image calls can take several minutes.",
            flush=True,
        )

    try:
        result = run_team_pipeline(
            DemoRequest(
                prompt=args.prompt,
                mode="verified",
                max_repair_attempts=args.max_text_repairs,
            ),
            services,
            include_visuals=args.visuals,
            max_visual_repairs=args.max_visual_repairs,
        )

    finally:
        configure_verifier(None)

    # Give each run a separate output folder.
    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    destination = (
        root
        / "outputs"
        / "team_demo"
        / f"{stamp}_{uuid4().hex[:8]}"
    )

    destination.mkdir(
        parents=True,
        exist_ok=False,
    )

    # Save the results, never API keys or environment settings.
    (destination / "result.json").write_text(
        json.dumps(
            _serialize(result),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (destination / "scene.txt").write_text(
        result.text.final_scene.text,
        encoding="utf-8",
    )

    print("\nText status:", result.text.status)
    print("Initial scene:", result.text.initial_scene.text)
    print("Final scene:", result.text.final_scene.text)
    print("Repair calls:", result.text.repair_attempts)

    for number, report in enumerate(
        result.text.reports,
        start=1,
    ):
        print(
            f"\nText check {number}:",
            report.summary.model_dump(),
        )

        for claim in report.claims:
            print(
                f"  [{claim.classification.value}] "
                f"{claim.claim}"
            )
            print(
                f"    {claim.reason} "
                f"Evidence: {claim.evidence_fact_ids}"
            )

    print("\nVisual status:", result.visual_status)

    if result.asset:
        print("Image:", result.asset.image_path)

    for reason in result.visual_review_reasons:
        print("  Review:", reason)

    if result.visual_error:
        print(result.visual_error)

    print("Saved run:", destination)


if __name__ == "__main__":
    main()