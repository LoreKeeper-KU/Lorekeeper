# Authored by Abdullah on 17/11/2026
# Runs the scripted generation demo with Faris's real continuity checker.

from pathlib import Path

from dotenv import load_dotenv


def main():
    # Load the main repository's environment before importing the AI client.
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    from shared.ai_client import AIClient
    from continuity_checker.addition_judge import LLMAdditionJudge
    from continuity_checker.canon_verifier import CanonVerifier
    from continuity_checker.checker import configure_verifier
    from continuity_checker.claim_extractor import (
        ClaimExtractor,
        SharedClientClaimProposer,
    )
    from continuity_checker.contradiction_classifier import (
        ContradictionClassifier,
    )
    from continuity_checker.nli_comparator import NLIComparator

    from .models import DemoRequest
    from .orchestrator import run_pipeline

    # Both claim extraction and addition judging use this shared client.
    client = AIClient()

    print("Loading the continuity model...")

    # Load the NLI model once, then reuse it for every verification.
    comparator = NLIComparator.from_pretrained(
        "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    )

    verifier = CanonVerifier(
        # Extract atomic claims and check their exact source quotes.
        extractor=ClaimExtractor(
            SharedClientClaimProposer(client)
        ),

        # Compare each claim with the relevant canon.
        comparator=comparator,

        # Classify the result, consulting the addition judge when needed.
        classifier=ContradictionClassifier(
            addition_judge=LLMAdditionJudge(client)
        ),
    )

    # Register the verifier used by the orchestrator's verify_scene() call.
    configure_verifier(verifier)

    request = DemoRequest(
        prompt="Write a scene where Princess Amina defends her castle.",
        mode="verified",
        max_repair_attempts=3,
    )

    print("Running generation, verification, and repair...")

    try:
        result = run_pipeline(request)
    finally:
        # Clear the registered verifier when the demo finishes.
        configure_verifier(None)

    print("\nStatus:", result.status)
    print("Initial scene:", result.initial_scene.text)
    print("Final scene:", result.final_scene.text)
    print("Repair attempts:", result.repair_attempts)

    # Show the evidence behind each decision.
    for number, report in enumerate(result.reports, start=1):
        print(f"\nVerification {number}:")
        print("Summary:", report.summary.model_dump())

        for assessment in report.claims:
            print(
                f"- [{assessment.classification.value}] "
                f"{assessment.claim}"
            )
            print("  Reason:", assessment.reason)
            print("  Evidence:", assessment.evidence_fact_ids)


if __name__ == "__main__":
    main()