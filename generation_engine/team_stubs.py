# Authored by Abdullah on 31/10/2026
# Temporary sample functions for the other team members' modules.
# These are placeholders so your workflow can run before their real code is ready.


from shared.schemas import (
    CanonFact,
    ClaimAssessment,
    ClaimClassification,
    VerificationReport,
)


def retrieve_canon(query: str) -> list[CanonFact]:
    """
    Return sample canon using the agreed interface.

    The query is accepted for compatibility. This mock always
    returns the same facts until real retrieval is connected.
    """
    return [
        CanonFact(
            id="fact-001",
            subject="Princess Amina",
            predicate="ability",
            object="no magical ability",
        ),
        CanonFact(
            id="fact-002",
            subject="Princess Amina",
            predicate="location",
            object="Silverkeep Castle",
        ),
        CanonFact(
            id="fact-003",
            subject="Princess Amina",
            predicate="commands",
            object="archers",
        ),
    ]


def verify_scene(
    scene: str,
    canon_facts: list[CanonFact],
) -> VerificationReport:
    """
    Return a shared VerificationReport for the fixed demo.

    Faris's real verifier will replace this limited mock.
    """

    # Find the relevant facts in the canon actually supplied.
    ability_fact = next(
        (
            fact
            for fact in canon_facts
            if fact.subject == "Princess Amina"
            and fact.predicate == "ability"
            and fact.object == "no magical ability"
        ),
        None,
    )

    archers_fact = next(
        (
            fact
            for fact in canon_facts
            if fact.subject == "Princess Amina"
            and fact.predicate == "commands"
            and fact.object == "archers"
        ),
        None,
    )

    # Recognize the initial demo contradiction.
    if "magical firestorm" in scene:
        if ability_fact is not None:
            return VerificationReport(
                claims=[
                    ClaimAssessment(
                        claim="Princess Amina summons a magical firestorm.",
                        classification=ClaimClassification.CONTRADICTION,
                        reason="Canon states that Amina has no magical ability.",
                        evidence_fact_ids=[ability_fact.id],
                    )
                ]
            )

    # Recognize the repaired demo action.
    elif "commanded her archers" in scene:
        if archers_fact is not None:
            return VerificationReport(
                claims=[
                    ClaimAssessment(
                        claim="Princess Amina commands archers.",
                        classification=ClaimClassification.SUPPORTED,
                        reason="Canon establishes that Amina commands archers.",
                        evidence_fact_ids=[archers_fact.id],
                    )
                ]
            )

    # Unknown text or missing evidence must not automatically pass.
    return VerificationReport(
        claims=[
            ClaimAssessment(
                claim="The scene follows the supplied canon.",
                classification=ClaimClassification.UNCERTAIN,
                reason=(
                    "This demo mock cannot assess the supplied scene "
                    "with the available evidence."
                ),
                evidence_fact_ids=[],
            )
        ]
    )


def generate_image(scene_text: str):
    """
    Unused visual placeholder for the demo.

    Saif's actual visual functions will be connected separately.
    No image is generated here.
    """
    return {
        "status": "not_implemented",
        "message": "Image generation will be connected later.",
        "scene_text": scene_text,
    }