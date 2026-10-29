"""LoreKeeper / GENERATION & REPAIR (Owner: Abdullah)
======================================================
Purpose:
    Generate scenes and, after receiving Faris's verification report,
    repair canon contradictions while keeping useful narrative detail.

EXAMPLE INPUT TO generate_scene():
    prompt = "Write a scene where Captain Arin visits Queen Lyra in Eldoria."
    canon_facts = [
        CanonFact(id="fact-001", subject="Captain Arin",
                  predicate="weapon", object="golden spear"),
        CanonFact(id="fact-002", subject="Queen Lyra",
                  predicate="rules", object="Eldoria"),
        CanonFact(id="fact-003", subject="Captain Arin's father",
                  predicate="status", object="alive"),
    ]

EXAMPLE OUTPUT FROM generate_scene():
    "Captain Arin entered the royal palace in Eldoria. "
    "He drew his silver sword and approached Queen Lyra. "
    "The queen greeted him warmly. "
    "Arin remembered that his father had died in the Great War."

    (This initial generation contains a contradiction on purpose;
     Faris's checker should detect it.)

EXAMPLE INPUT TO repair_scene():
    scene = <the generated scene above>
    report = VerificationReport(
        claims=[
            ClaimAssessment(
                claim="Arin's father died in the Great War.",
                classification=ClaimClassification.CONTRADICTION,
                reason="Established canon says his father is alive.",
                evidence_fact_ids=["fact-003"],
            )
        ]
    )
    canon_facts = <the same list above>

EXPECTED OUTPUT FROM repair_scene():
    "Captain Arin entered the royal palace in Eldoria. "
    "He drew his silver sword and approached Queen Lyra. "
    "The queen greeted him warmly. "
    "Arin thought of his father, who was still alive."

    The explicitly contradictory sentence is repaired. The sword is
    *not* silently treated as a contradiction; Faris marked it uncertain.
    A later policy can decide whether uncertain details are kept,
    removed, or sent to a human reviewer.

YOUR TODOs:
    1. Call an LLM to generate scene text from prompt + relevant canon.
    2. Use Faris's contradiction report to construct repair feedback.
    3. Revise only the necessary claims, preserving story flow.
    4. Coordinate a bounded "generate -> check -> repair -> recheck"
       loop with the app-level orchestrator.
    5. Add tests for preserving non-contradictory story details.

INTEGRATION CONTRACT:
    Takes canon from Abdulaziz and verification reports from Faris.
    Returns a plain story string that Saif can illustrate.
"""

from shared.schemas import CanonFact, VerificationReport


def generate_scene(prompt: str, canon_facts: list[CanonFact]) -> str:
    """Generate a candidate scene using the supplied canon context."""
    # TODO (Abdullah): Call your LLM provider and return scene text.
    raise NotImplementedError("Abdullah: implement generate_scene")


def repair_scene(
    scene: str,
    report: VerificationReport,
    canon_facts: list[CanonFact],
) -> str:
    """Rewrite canon contradictions without discarding valid additions."""
    # TODO (Abdullah): Address CONTRADICTION claims with canon evidence.
    # TODO (Abdullah): Decide how to handle UNCERTAIN claims in policy.
    raise NotImplementedError("Abdullah: implement repair_scene")
