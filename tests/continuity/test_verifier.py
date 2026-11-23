# Authored by Faris
from continuity_checker.canon_verifier import CanonVerifier, Verdict
from continuity_checker.claim_extractor import ClaimExtractor, ProposedClaim
from continuity_checker.contradiction_classifier import ContradictionClassifier
from continuity_checker.models import (
    CanonFact,
    Claim,
    ClaimClassification,
    Scene,
    SourceSpan,
    VerificationReport,
)

FIREBALL = "Amina can summon magical firestorms."

F001 = CanonFact(
    id="F001", subject="char_amina", predicate="rules", object="Northern_Kingdom"
)
F002 = CanonFact(
    id="F002", subject="char_amina", predicate="magic_ability", object="none"
)


def scripted_comparator(table):
    """Fake NLI: looks up (claim text, fact id); anything unlisted is neutral."""

    def comparator(claim, fact):
        return table.get((claim.text, fact.id), Verdict.NEUTRAL)

    return comparator


def make_verifier(table=None, proposals=(), judge=None):
    return CanonVerifier(
        extractor=ClaimExtractor(lambda text: list(proposals)),
        comparator=scripted_comparator(table or {}),
        classifier=ContradictionClassifier(judge),
    )


def make_claim(text=FIREBALL):
    return Claim(claim_id="C001", text=text, source_span=SourceSpan(start=0, end=10))


def test_verify_claim_classifies_a_contradiction_and_cites_the_fact():
    verifier = make_verifier({(FIREBALL, "F002"): Verdict.CONTRADICTION})

    result = verifier.verify_claim(make_claim(), [F001, F002])

    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F002"]


def test_verify_claim_passes_the_judge_through_for_neutral_claims():
    verifier = make_verifier(judge=lambda claim, evidence: True)

    result = verifier.verify_claim(make_claim("Amina carries a shield."), [F001, F002])

    assert result.classification == ClaimClassification.VALID_NEW_ADDITION


AMINA_SCENE = Scene(
    scene_id="scene_001",
    world_id="world_001",
    text=(
        "Princess Amina raised her hands and summoned a magical firestorm "
        "to destroy the invading army."
    ),
)


def amina_verifier():
    return make_verifier(
        {(FIREBALL, "F002"): Verdict.CONTRADICTION},
        proposals=[ProposedClaim(text=FIREBALL, quote=AMINA_SCENE.text)],
    )


def test_verify_claims_keeps_the_claim_id_evidence_and_passage_span():
    (claim,) = amina_verifier().verify_claims(AMINA_SCENE, [F002])

    assert claim.claim_id == "C001"
    assert claim.classification == ClaimClassification.CONTRADICTION
    assert claim.evidence_ids == ["F002"]
    assert AMINA_SCENE.text[claim.source_span.start : claim.source_span.end] == AMINA_SCENE.text


def test_verify_scene_returns_the_team_report_for_the_firestorm_contradiction():
    report = amina_verifier().verify_scene(AMINA_SCENE, [F002])

    assert isinstance(report, VerificationReport)
    assert report.summary.contradictions == 1
    (assessment,) = report.claims
    assert assessment.claim == FIREBALL
    assert assessment.classification == ClaimClassification.CONTRADICTION
    assert assessment.evidence_fact_ids == ["F002"]


def test_scene_with_no_claims_yields_an_empty_team_report():
    report = make_verifier().verify_scene(AMINA_SCENE, [F002])

    assert report.claims == []
    assert report.summary.contradictions == 0
    assert report.summary.uncertain == 0


DEMO_SENTENCES = [
    "Amina rules the Northern Kingdom.",
    "She carried a decorated shield.",
    "She raised her hands and summoned a magical firestorm.",
    "She whispered about her secret sibling.",
]
DEMO_SCENE = Scene(scene_id="scene_002", world_id="world_001", text=" ".join(DEMO_SENTENCES))
DEMO_PROPOSALS = [
    ProposedClaim(text="Amina rules the Northern Kingdom.", quote=DEMO_SENTENCES[0]),
    ProposedClaim(text="Amina carries a decorated shield.", quote=DEMO_SENTENCES[1]),
    ProposedClaim(text=FIREBALL, quote=DEMO_SENTENCES[2]),
    ProposedClaim(text="Amina has a secret sibling.", quote=DEMO_SENTENCES[3]),
]


def demo_verifier():
    return make_verifier(
        {
            ("Amina rules the Northern Kingdom.", "F001"): Verdict.ENTAILMENT,
            (FIREBALL, "F002"): Verdict.CONTRADICTION,
        },
        proposals=DEMO_PROPOSALS,
        judge=lambda claim, evidence: "shield" in claim.text,
    )


def test_one_scene_yields_all_four_categories_with_spans_that_locate_each_passage():
    claims = demo_verifier().verify_claims(DEMO_SCENE, [F001, F002])

    by_category = {c.classification: c for c in claims}
    assert set(by_category) == set(ClaimClassification)
    assert by_category[ClaimClassification.SUPPORTED].evidence_ids == ["F001"]
    assert by_category[ClaimClassification.CONTRADICTION].evidence_ids == ["F002"]
    assert by_category[ClaimClassification.VALID_NEW_ADDITION].evidence_ids == []
    assert by_category[ClaimClassification.UNCERTAIN].evidence_ids == []

    passages = {
        c.classification: DEMO_SCENE.text[c.source_span.start : c.source_span.end]
        for c in claims
    }
    assert passages[ClaimClassification.CONTRADICTION] == DEMO_SENTENCES[2]
    assert passages[ClaimClassification.UNCERTAIN] == DEMO_SENTENCES[3]


def test_the_four_category_scene_summarises_in_the_team_report():
    report = demo_verifier().verify_scene(DEMO_SCENE, [F001, F002])

    assert report.summary.model_dump() == {
        "supported": 1,
        "valid_new_additions": 1,
        "contradictions": 1,
        "uncertain": 1,
    }


BORIN = CanonFact(id="F009", subject="char_borin", predicate="occupation", object="blacksmith")


def recording_verifier(relevance=None, judge=None):
    compared = []

    def comparator(claim, fact):
        compared.append(fact.id)
        return Verdict.NEUTRAL

    kwargs = {} if relevance is None else {"relevance": relevance}
    verifier = CanonVerifier(
        extractor=ClaimExtractor(lambda text: []),
        comparator=comparator,
        classifier=ContradictionClassifier(judge),
        **kwargs,
    )
    return verifier, compared


def test_only_relevant_facts_reach_the_comparator():
    verifier, compared = recording_verifier()

    verifier.verify_claim(make_claim(), [F001, BORIN, F002])

    assert compared == ["F001", "F002"]


def test_the_judge_and_classifier_see_only_the_relevant_facts():
    seen = []

    def judge(claim, evidence):
        seen.append([fact.id for fact in evidence])
        return False

    verifier, _ = recording_verifier(judge=judge)

    verifier.verify_claim(make_claim(), [F001, BORIN, F002])

    assert seen == [["F001", "F002"]]


def test_a_named_claim_with_no_relevant_facts_is_uncertain_and_nothing_is_compared_or_judged():
    judged = []
    verifier, compared = recording_verifier(judge=lambda c, e: judged.append(1) or True)

    result = verifier.verify_claim(make_claim("Madame Orlova sold bread."), [F001, BORIN, F002])

    assert result.classification == ClaimClassification.UNCERTAIN
    assert compared == []
    assert judged == []


def test_scenery_with_no_relevant_facts_is_judged_against_all_the_supplied_canon():
    seen = []

    def judge(claim, evidence):
        seen.append([fact.id for fact in evidence])
        return True

    verifier, compared = recording_verifier(judge=judge)

    result = verifier.verify_claim(make_claim("The merchant sold bread."), [F001, BORIN, F002])

    assert result.classification == ClaimClassification.VALID_NEW_ADDITION
    assert compared == []  # nothing is related, so the NLI model is not asked
    assert seen == [["F001", "F009", "F002"]]


def test_the_relevance_function_can_be_replaced():
    verifier, compared = recording_verifier(relevance=lambda claim, facts: facts)

    verifier.verify_claim(make_claim(), [F001, BORIN, F002])

    assert compared == ["F001", "F009", "F002"]
