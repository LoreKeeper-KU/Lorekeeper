# Authored by Abdullah on 31/10/2026
# This file contains your story-generation and repair functions.
# The text is scripted for the demo. Later, you can replace it
# with a call to the shared ai_client.py.


from shared.schemas import (
    CanonFact,
    ClaimClassification,
    VerificationReport,
)


def generate_scene(
    prompt: str,
    canon_facts: list[CanonFact],
) -> str:
    """
    Creates the first version of a scene.
    """

    return (
        "Princess Amina stood on the walls of Silverkeep Castle. "
        "She summoned a magical firestorm to drive back the attackers."
    )


def repair_scene(
    scene: str,
    report: VerificationReport,
    canon_facts: list[CanonFact],
) -> str:
    """
    Repairs only the contradictory part of the scene.
    """

    has_contradiction = any(
        claim.classification == ClaimClassification.CONTRADICTION
        for claim in report.claims
    )

    if has_contradiction:
        return scene.replace(
            "She summoned a magical firestorm to drive back the attackers.",
            "She commanded her archers to fire flaming arrows at the attackers.",
        )

    return scene