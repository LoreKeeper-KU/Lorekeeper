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

from shared.schemas import CanonFact, VerificationReport


def verify_scene(scene: str, canon_facts: list[CanonFact]) -> VerificationReport:
    """Return one ClaimAssessment for each distinct claim in the scene."""
    # TODO (Faris): Extract claims and check each against canon.
    # TODO (Faris): Return VerificationReport(claims=[...]).
    raise NotImplementedError("Faris: implement verify_scene")
