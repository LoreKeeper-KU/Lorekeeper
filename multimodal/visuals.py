# Authored By Saif Altamimi 31/10/2026
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
from shared.ai_client import AIClient
from shared.schemas import CanonFact, VisualAsset, VisualReport
from multimodal.model import VisionCheckResult

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


def generate_visual(
        scene: str,
        canon_facts: list[CanonFact],
        ai: AIClient | None = None) -> VisualAsset:
    """Generate an image for a repaired scene and return its metadata."""
    ai = ai or AIClient()
    # 1. Build the prompt from the scene and facts
    prompt = build_visual_prompt(scene, canon_facts)
    # 2. Ask the AI client to generate an image from that prompt
    image_path = ai.generate_image(prompt) 
    # 3. Package the image path and prompt into a VisualAsset and return it
    return VisualAsset(image_path=image_path, prompt=prompt)



VERIFY_INSTRUCTIONS = """You are checking an illustration against established story facts.
For EACH fact below, judge only what is actually visible in the image:
- "match": clearly visible and agrees with the fact.
- "mismatch": clearly visible and contradicts the fact.
- "unable_to_assess": hidden, too small, unclear, or not something a picture
  can show (for example, who rules a kingdom).
Details that the facts do not mention are NOT mismatches.
Never guess. Copy each fact_id exactly as given."""

def build_verify_prompt(canon_facts: list[CanonFact]) -> str:
    """List the facts for the vision model, each with its id."""
    lines = [VERIFY_INSTRUCTIONS, "", "Facts to check:"]
    for fact in canon_facts:
        predicate = fact.predicate.replace("_", " ")
        lines.append(f"- {fact.id}: {fact.subject} | {predicate} | {fact.object}")
    return "\n".join(lines)

def verify_visual(
    asset: VisualAsset,
    canon_facts: list[CanonFact],
    ai: AIClient | None = None,
) -> VisualReport:
    """Assess whether a generated image agrees with retrieved canon."""
    ai = ai or AIClient()



        # 1. Ask the vision model to check every fact against the actual image
    result = ai.analyze_image(
        asset.image_path, build_verify_prompt(canon_facts), schema=VisionCheckResult
    )

        # 2. Keep only real mismatches about facts we actually sent
    #    (ignores any fact_id the model invented)
    facts_by_id = {fact.id: fact for fact in canon_facts}
    mismatches = [
        check
        for check in result.checks
        if check.status == "mismatch" and check.fact_id in facts_by_id
    ]

        # 3. Turn each mismatch into a readable issue, linked to its fact id
    issues = []
    for check in mismatches:
        fact = facts_by_id[check.fact_id]
        predicate = fact.predicate.replace("_", " ")
        issues.append(
            f"{fact.subject} {predicate}: expected '{fact.object}', "
            f"image shows '{check.observed}'. {check.explanation}"
        )

        # 4. Package everything into the shared VisualReport
    return VisualReport(
        image_path=asset.image_path,
        consistent=not mismatches,
        issues=issues,
        evidence_fact_ids=[check.fact_id for check in mismatches],
    )
    

