"""LoreKeeper / MULTIMODAL VISUALS (Owner: Saif)
=================================================
Purpose:
    Turn an accepted/repaired scene into a visual prompt and an image,
    then check the resulting image against relevant visual canon.

EXAMPLE INPUT TO generate_visual():
    scene = (
        "Captain Arin entered the royal palace in Eldoria. "
        "Queen Lyra greeted him warmly. "
        "Arin thought of his father, who was still alive."
    )
    canon_facts = [
        CanonFact(id="fact-001", subject="Captain Arin",
                  predicate="weapon", object="golden spear"),
        CanonFact(id="fact-002", subject="Queen Lyra",
                  predicate="rules", object="Eldoria"),
    ]

EXPECTED OUTPUT FROM generate_visual() (illustrative):
    VisualAsset(
        image_path="outputs/arin_palace.png",
        prompt=(
            "Illustrate Captain Arin meeting Queen Lyra inside Eldoria's "
            "royal palace. Arin carries his canonical golden spear. "
            "Avoid introducing visual details that conflict with canon."
        ),
    )

EXAMPLE INPUT TO verify_visual():
    asset = VisualAsset(
        image_path="outputs/arin_palace.png",
        prompt="Illustrate Arin carrying the golden spear beside Queen Lyra.",
    )
    canon_facts = <the same list above>

EXPECTED OUTPUT FROM verify_visual() IF the generated image shows a
blue staff instead of the canonical golden spear:
    VisualReport(
        image_path="outputs/arin_palace.png",
        consistent=False,
        issues=[
            "Arin appears to carry a blue staff instead of a golden spear."
        ],
        evidence_fact_ids=["fact-001"],
    )

    A visually consistent image would return consistent=True and
    issues=[] instead. These examples are not actual generated images.

YOUR TODOs:
    1. Build an image-generation prompt from a repaired scene + canon.
    2. Call an image generation model/API and persist the output.
    3. Check the image with a vision-capable model, using canon as context.
    4. Return an evidence-based VisualReport; do not invent mismatches.
    5. Decide how to handle visual contradictions (retry or human review).

INTEGRATION CONTRACT:
    Receives Abdullah's repaired story and Abdulaziz's canon.
    Keep the image path and verification result separate from story text.
"""

from shared.schemas import CanonFact, VisualAsset, VisualReport

STYLE = "A cinematic fantasy illustration."


def build_visual_prompt(scene: str, canon_facts: list[CanonFact]) -> str:
    """Turn a scene and its canon facts into a prompt for the image model."""
    lines = [STYLE, f"Scene: {scene}"]

    if canon_facts:
        lines.append("Respect these established facts about the world:")
        for fact in canon_facts:
            predicate = fact.predicate.replace("_", " ")
            lines.append(f"- {fact.subject} ({predicate}): {fact.object}")

    lines.append("Avoid visual details that conflict with these facts.")
    return "\n".join(lines)


def generate_visual(scene: str, canon_facts: list[CanonFact]) -> VisualAsset:
    """Generate an image for a repaired scene and return its metadata."""
    # TODO (Saif): Compose the prompt and call image generation.
    raise NotImplementedError("Saif: implement generate_visual")


def verify_visual(
    asset: VisualAsset,
    canon_facts: list[CanonFact],
) -> VisualReport:
    """Assess whether a generated image agrees with retrieved canon."""
    # TODO (Saif): Inspect asset.image_path with a vision model.
    raise NotImplementedError("Saif: implement verify_visual")
