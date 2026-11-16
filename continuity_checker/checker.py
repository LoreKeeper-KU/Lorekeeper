"""LoreKeeper / CONTINUITY CHECKER (Owner: Faris)
===================================================
Purpose:
    Extract claims from a generated scene, compare them with retrieved
    canon, and classify each claim. This module DOES NOT repair text.

EXAMPLE INPUT:
    scene = (
        "Captain Arin entered the royal palace in Eldoria. "
        "He drew his silver sword and approached Queen Lyra. "
        "The queen greeted him warmly. "
        "Arin remembered that his father had died in the Great War."
    )

    canon_facts = [
        CanonFact(
            id="fact-001", subject="Captain Arin",
            predicate="weapon", object="golden spear"
        ),
        CanonFact(
            id="fact-002", subject="Queen Lyra",
            predicate="rules", object="Eldoria"
        ),
        CanonFact(
            id="fact-003", subject="Captain Arin's father",
            predicate="status", object="alive"
        ),
    ]

EXPECTED OUTPUT (equivalent to VerificationReport.model_dump(mode="json")):
    {
      "claims": [
        {
          "claim": "Arin entered the royal palace in Eldoria.",
          "classification": "VALID_NEW_ADDITION",
          "reason": "Canon does not prohibit this visit.",
          "evidence_fact_ids": []
        },
        {
          "claim": "Arin drew a silver sword.",
          "classification": "UNCERTAIN",
          "reason": "A golden spear is known; sword ownership is not established. The spear may not be exclusive.",
          "evidence_fact_ids": ["fact-001"]
        },
        {
          "claim": "Queen Lyra rules Eldoria.",
          "classification": "SUPPORTED",
          "reason": "The retrieved canon explicitly establishes her rule.",
          "evidence_fact_ids": ["fact-002"]
        },
        {
          "claim": "Queen Lyra greeted Arin warmly.",
          "classification": "VALID_NEW_ADDITION",
          "reason": "No relevant canon conflicts with this interaction.",
          "evidence_fact_ids": []
        },
        {
          "claim": "Arin's father died in the Great War.",
          "classification": "CONTRADICTION",
          "reason": "Established canon says his father is alive.",
          "evidence_fact_ids": ["fact-003"]
        }
      ]
    }

Notes:
    - These are *illustrative* classifications, not ground truth.
    - "VALID_NEW_ADDITION" vs "UNCERTAIN" requires a stated policy;
      missing information alone does not prove contradiction.
    - The Queen Lyra claim is an interpretation of her title; only
      extract it if your claim extraction method supports that inference.

YOUR TODOs:
    1. Extract atomic claims from scene text.
    2. Align each claim to relevant canon facts.
    3. Assign one of four ClaimClassification values.
    4. Cite evidence_fact_ids and explain each decision.
    5. Validate the response with Pydantic and test edge cases.

INTEGRATION CONTRACT:
    Inputs come from Abdullah's generated scene and Abdulaziz's canon.
    Output goes to Abdullah for self-repair.
"""

from typing import Optional

from continuity_checker.canon_verifier import CanonVerifier
from continuity_checker.models import Scene
from shared.schemas import CanonFact, VerificationReport

# Temporary wiring until the shared AI client exists: the app (or a test) registers a
# fully built CanonVerifier. This module never creates an LLM client of its own.
_verifier: Optional[CanonVerifier] = None


class VerifierNotConfiguredError(RuntimeError):
    """verify_scene() was called before a CanonVerifier was registered."""


def configure_verifier(verifier: Optional[CanonVerifier]) -> None:
    """Register the CanonVerifier used by verify_scene(); pass None to clear it."""
    global _verifier
    _verifier = verifier


def verify_scene(scene: str, canon_facts: list[CanonFact]) -> VerificationReport:
    """Return one ClaimAssessment for each distinct claim in the scene."""
    if _verifier is None:
        raise VerifierNotConfiguredError(
            "No verifier is configured. Call continuity_checker.checker."
            "configure_verifier(CanonVerifier(...)) before verify_scene()."
        )
    # The team contract passes plain text, so the internal Scene gets placeholder IDs.
    return _verifier.verify_scene(Scene(scene_id="scene", world_id="world", text=scene), canon_facts)
