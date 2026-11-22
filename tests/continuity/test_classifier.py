# Authored by Faris
from continuity_checker.canon_verifier import ClaimComparison, Verdict
from continuity_checker.contradiction_classifier import ContradictionClassifier
from continuity_checker.models import CanonFact, Claim, ClaimClassification, SourceSpan


def make_claim():
    return Claim(
        claim_id="C001",
        text="Amina can summon magical firestorms.",
        source_span=SourceSpan(start=20, end=70),
    )


def make_rules_claim():
    """A claim that restates F003 (rules: Northern_Kingdom), so that fact may support it."""
    return Claim(
        claim_id="C001",
        text="Amina rules the Northern Kingdom.",
        source_span=SourceSpan(start=0, end=33),
    )


def make_fact(fact_id, predicate="magic_ability", value="none"):
    return CanonFact(
        id=fact_id,
        subject="char_amina",
        predicate=predicate,
        object=value,
    )


def comparison(verdict, supporting=(), conflicting=()):
    return ClaimComparison(
        claim_id="C001",
        verdict=verdict,
        supporting_fact_ids=list(supporting),
        conflicting_fact_ids=list(conflicting),
    )


F002 = make_fact("F002")
F003 = make_fact("F003", predicate="rules", value="Northern_Kingdom")


def test_contradiction_cites_the_conflicting_facts_and_keeps_the_claim_and_span():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F002"]), [F002, F003]
    )
    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F002"]
    assert (result.claim_id, result.text) == ("C001", "Amina can summon magical firestorms.")
    assert result.source_span == SourceSpan(start=20, end=70)


def test_contradiction_explanation_cites_the_fact_and_suggests_a_revision():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F002"]), [F002, F003]
    )
    assert "F002" in result.explanation
    assert "char amina magic ability: none" in result.explanation
    assert "F002" in result.suggested_action


def test_entailment_is_supported_and_cites_the_supporting_facts():
    result = ContradictionClassifier().classify(
        make_rules_claim(), comparison(Verdict.ENTAILMENT, supporting=["F003"]), [F002, F003]
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F003"]
    assert "F003" in result.explanation
    assert "char amina rules: Northern_Kingdom" in result.explanation
    assert result.suggested_action is None


def test_neutral_defaults_to_uncertain_and_never_to_a_new_addition():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002, F003]
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == []
    assert "neither supports nor contradicts" in result.explanation
    assert result.suggested_action is None


def test_neutral_with_no_canon_evidence_says_so():
    result = ContradictionClassifier().classify(make_claim(), comparison(Verdict.NEUTRAL), [])
    assert result.classification == ClaimClassification.UNCERTAIN
    assert "No canon evidence" in result.explanation


def approving(claim, canon_evidence):
    return True


def declining(claim, canon_evidence):
    return False


def must_not_be_called(claim, canon_evidence):
    raise AssertionError("AdditionJudge must only be consulted for neutral claims with evidence")


def test_neutral_becomes_a_new_addition_only_when_the_judge_approves():
    result = ContradictionClassifier(approving).classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002]
    )
    assert result.classification == ClaimClassification.VALID_NEW_ADDITION
    assert result.evidence_ids == []
    assert "approval" in result.explanation


def test_neutral_stays_uncertain_when_the_judge_declines():
    result = ContradictionClassifier(declining).classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002]
    )
    assert result.classification == ClaimClassification.UNCERTAIN


def test_judge_receives_the_claim_and_the_canon_evidence():
    seen = []

    def judge(claim, canon_evidence):
        seen.append((claim.claim_id, [f.id for f in canon_evidence]))
        return False

    ContradictionClassifier(judge).classify(
        make_claim(), comparison(Verdict.NEUTRAL), [F002, F003]
    )
    assert seen == [("C001", ["F002", "F003"])]


def test_judge_is_not_consulted_for_contradiction_or_supported_claims():
    classifier = ContradictionClassifier(must_not_be_called)
    contradicted = classifier.classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F002"]), [F002]
    )
    supported = classifier.classify(
        make_claim(), comparison(Verdict.ENTAILMENT, supporting=["F002"]), [F002]
    )
    assert contradicted.classification == ClaimClassification.CONTRADICTION
    assert supported.classification == ClaimClassification.SUPPORTED


def test_no_canon_evidence_stays_uncertain_even_if_the_judge_would_approve():
    result = ContradictionClassifier(approving).classify(
        make_claim(), comparison(Verdict.NEUTRAL), []
    )
    assert result.classification == ClaimClassification.UNCERTAIN


SPEAR = make_fact("F010", predicate="weapon", value="golden spear")
ALIVE = make_fact("F011", predicate="status", value="alive")


def test_a_conflict_with_a_non_exclusive_fact_stays_uncertain_and_cites_it():
    result = ContradictionClassifier(must_not_be_called).classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F010"]), [SPEAR]
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == ["F010"]
    assert "F010" in result.explanation
    assert "not accepted as a contradiction" in result.explanation
    assert result.suggested_action is None


def test_a_conflict_with_an_exclusive_fact_is_still_a_contradiction():
    result = ContradictionClassifier().classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F011"]), [ALIVE]
    )
    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F011"]


def test_a_conflict_with_a_relationship_fact_is_a_contradiction():
    for predicate, value in [("father", "Eli"), ("mother", "Odette"), ("house", "House Mori"),
                             ("allegiance", "the Guild")]:
        fact = make_fact("F020", predicate=predicate, value=value)
        result = ContradictionClassifier(must_not_be_called).classify(
            make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F020"]), [fact]
        )
        assert result.classification == ClaimClassification.CONTRADICTION, predicate
        assert result.evidence_ids == ["F020"]


def test_only_the_exclusive_facts_are_cited_when_conflicts_are_mixed():
    result = ContradictionClassifier().classify(
        make_claim(),
        comparison(Verdict.CONTRADICTION, conflicting=["F010", "F011"]),
        [SPEAR, ALIVE],
    )
    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F011"]


def test_a_rejected_conflict_does_not_overrule_real_support():
    result = ContradictionClassifier().classify(
        make_rules_claim(),
        comparison(Verdict.CONTRADICTION, supporting=["F003"], conflicting=["F010"]),
        [F003, SPEAR],
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F003"]


def test_the_exclusivity_check_can_be_replaced():
    result = ContradictionClassifier(exclusive=lambda fact: True).classify(
        make_claim(), comparison(Verdict.CONTRADICTION, conflicting=["F010"]), [SPEAR]
    )
    assert result.classification == ClaimClassification.CONTRADICTION


# ---- a conflict only counts when the claim is about the fact's attribute ----

def kael_claim(text):
    return Claim(claim_id="C001", text=text, source_span=SourceSpan(start=0, end=len(text)))


HAIR = CanonFact(id="F030", subject="Kael", predicate="hair_color", object="black")
EYES = CanonFact(id="F031", subject="Kael", predicate="eye_color", object="green")
NO_MAGIC = CanonFact(id="F032", subject="Kael", predicate="magic_ability", object="none")
JOB = CanonFact(id="F033", subject="Kael", predicate="occupation", object="cartographer")


def test_a_conflict_with_an_exclusive_fact_the_claim_is_not_about_is_ignored():
    result = ContradictionClassifier().classify(
        kael_claim("Kael had a pack mule."),
        comparison(Verdict.CONTRADICTION, conflicting=["F030", "F031", "F032"]),
        [HAIR, EYES, NO_MAGIC],
    )
    assert result.classification != ClaimClassification.CONTRADICTION
    assert result.evidence_ids == []
    assert "conflict" not in result.explanation.lower()


def test_an_ignored_conflict_does_not_hide_real_support():
    supporting = CanonFact(id="F034", subject="Kael", predicate="pet", object="pack mule")
    result = ContradictionClassifier().classify(
        kael_claim("Kael had a pack mule."),
        comparison(Verdict.CONTRADICTION, supporting=["F034"], conflicting=["F030"]),
        [supporting, HAIR],
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F034"]


def test_a_real_conflict_is_still_accepted_beside_an_ignored_one():
    result = ContradictionClassifier().classify(
        kael_claim("Kael has blue eyes."),
        comparison(Verdict.CONTRADICTION, conflicting=["F030", "F031"]),
        [HAIR, EYES],
    )
    assert result.classification == ClaimClassification.CONTRADICTION
    assert result.evidence_ids == ["F031"]


def test_an_ignored_conflict_leaves_the_claim_to_the_addition_judge():
    asked = []

    def judge(claim, evidence):
        asked.append([fact.id for fact in evidence])
        return True

    result = ContradictionClassifier(judge).classify(
        kael_claim("Kael had a pack mule."),
        comparison(Verdict.CONTRADICTION, conflicting=["F030"]),
        [HAIR],
    )
    assert asked == [["F030"]]
    assert result.classification == ClaimClassification.VALID_NEW_ADDITION


def test_a_conflict_with_a_non_exclusive_fact_the_claim_is_not_about_is_ignored():
    """"Kael brushed moss from the road" is not about his occupation, whatever the NLI says."""
    result = ContradictionClassifier().classify(
        kael_claim("Kael brushed moss from the road."),
        comparison(Verdict.CONTRADICTION, conflicting=["F033"]),
        [JOB],
    )
    assert result.evidence_ids == []
    assert "conflict" not in result.explanation.lower()


def test_an_ignored_non_exclusive_conflict_leaves_the_claim_to_the_addition_judge():
    asked = []

    def judge(claim, evidence):
        asked.append([fact.id for fact in evidence])
        return True

    result = ContradictionClassifier(judge).classify(
        kael_claim("Kael brushed moss from the road."),
        comparison(Verdict.CONTRADICTION, conflicting=["F033"]),
        [JOB],
    )
    assert asked == [["F033"]]
    assert result.classification == ClaimClassification.VALID_NEW_ADDITION


def test_a_conflict_with_a_non_exclusive_fact_the_claim_is_about_stays_uncertain():
    result = ContradictionClassifier(must_not_be_called).classify(
        kael_claim("Kael gave up his occupation and took up weaving."),
        comparison(Verdict.CONTRADICTION, conflicting=["F033"]),
        [JOB],
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == ["F033"]


def test_a_conflict_with_a_slot_fact_stays_uncertain_however_the_claim_is_worded():
    """A different weapon is tension even when the claim never says "weapon"."""
    result = ContradictionClassifier(must_not_be_called).classify(
        kael_claim("Kael drew a steel dagger."),
        comparison(Verdict.CONTRADICTION, conflicting=["F010"]),
        [SPEAR],
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == ["F010"]


def test_a_mix_of_ignored_and_real_non_exclusive_conflicts_cites_only_the_real_one():
    result = ContradictionClassifier().classify(
        kael_claim("Kael gave up his occupation and bought a pack mule."),
        comparison(Verdict.CONTRADICTION, conflicting=["F033", "F035"]),
        [JOB, CanonFact(id="F035", subject="Kael", predicate="flaw", object="He is stubborn.")],
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == ["F033"]


# ---- scenery that no canon fact is about may reach the judge, with the scene's canon ----

WORLD = [HAIR, EYES, NO_MAGIC, JOB]
BIRD = "A bird startled from a nearby pine."


def test_scenery_with_no_related_facts_is_judged_against_the_scenes_canon():
    asked = []

    def judge(claim, evidence):
        asked.append([fact.id for fact in evidence])
        return True

    result = ContradictionClassifier(judge).classify(
        kael_claim(BIRD), comparison(Verdict.NEUTRAL), [], world_facts=WORLD
    )
    assert result.classification == ClaimClassification.VALID_NEW_ADDITION
    assert asked == [["F030", "F031", "F032", "F033"]]
    assert "scene detail" in result.explanation.lower()


def test_scenery_stays_uncertain_when_the_judge_declines():
    result = ContradictionClassifier(declining).classify(
        kael_claim(BIRD), comparison(Verdict.NEUTRAL), [], world_facts=WORLD
    )
    assert result.classification == ClaimClassification.UNCERTAIN


def test_a_named_entity_is_never_judged_without_related_facts():
    result = ContradictionClassifier(must_not_be_called).classify(
        kael_claim("Madame Orlova runs the fish market."),
        comparison(Verdict.NEUTRAL),
        [],
        world_facts=WORLD,
    )
    assert result.classification == ClaimClassification.UNCERTAIN


def test_a_claim_that_does_not_read_as_scenery_is_never_judged_without_related_facts():
    result = ContradictionClassifier(must_not_be_called).classify(
        kael_claim("Zayd defended the city."), comparison(Verdict.NEUTRAL), [], world_facts=WORLD
    )
    assert result.classification == ClaimClassification.UNCERTAIN


def test_scenery_is_not_judged_when_there_is_no_canon_at_all():
    result = ContradictionClassifier(must_not_be_called).classify(
        kael_claim(BIRD), comparison(Verdict.NEUTRAL), [], world_facts=[]
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert "No canon evidence" in result.explanation


def test_scenery_is_not_judged_when_the_caller_supplies_no_scene_canon():
    """classify() called the old way, without world_facts, behaves exactly as before."""
    result = ContradictionClassifier(must_not_be_called).classify(
        kael_claim(BIRD), comparison(Verdict.NEUTRAL), []
    )
    assert result.classification == ClaimClassification.UNCERTAIN


def test_scenery_is_not_judged_a_second_time_when_related_facts_exist():
    asked = []

    def judge(claim, evidence):
        asked.append(len(evidence))
        return False

    ContradictionClassifier(judge).classify(
        kael_claim(BIRD), comparison(Verdict.NEUTRAL), [JOB], world_facts=WORLD
    )
    assert asked == [1]  # only the related-facts judgement


def test_a_scenery_conflict_the_nli_found_is_still_decided_by_the_normal_rules():
    result = ContradictionClassifier(must_not_be_called).classify(
        kael_claim("A bird perched on the bridge of Kael's occupation."),
        comparison(Verdict.CONTRADICTION, conflicting=["F033"]),
        [JOB],
        world_facts=WORLD,
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == ["F033"]


def test_a_judge_with_a_dedicated_scenery_method_uses_it_for_scenery_only():
    class Judge:
        def __init__(self):
            self.related, self.unrelated = [], []

        def __call__(self, claim, evidence):
            self.related.append(claim.text)
            return False

        def judge_unrelated(self, claim, world_facts):
            self.unrelated.append(claim.text)
            return True

    judge = Judge()
    classifier = ContradictionClassifier(judge)

    scenery = classifier.classify(kael_claim(BIRD), comparison(Verdict.NEUTRAL), [], world_facts=WORLD)
    related = classifier.classify(kael_claim("Kael had a pack mule."), comparison(Verdict.NEUTRAL), [JOB])

    assert scenery.classification == ClaimClassification.VALID_NEW_ADDITION
    assert related.classification == ClaimClassification.UNCERTAIN
    assert judge.unrelated == [BIRD]
    assert judge.related == ["Kael had a pack mule."]


def test_the_scene_detail_check_can_be_replaced():
    result = ContradictionClassifier(approving, is_scene_detail=lambda text: True).classify(
        kael_claim("Zayd defended the city."), comparison(Verdict.NEUTRAL), [], world_facts=WORLD
    )
    assert result.classification == ClaimClassification.VALID_NEW_ADDITION


# ---- a fact only supports a claim it is about ----

BUILD = CanonFact(id="F040", subject="Nora", predicate="build", object="lean")
SCOUT = CanonFact(id="F041", subject="Nora", predicate="occupation", object="scout")
KATANA = CanonFact(id="F042", subject="Nora", predicate="weapon", object="a curved katana")
STILL_ALIVE = CanonFact(id="F043", subject="Nora", predicate="status", object="alive")


def nora_claim(text):
    return Claim(claim_id="C001", text=text, source_span=SourceSpan(start=0, end=len(text)))


def test_support_from_a_fact_the_claim_is_not_about_is_ignored():
    asked = []

    def judge(claim, evidence):
        asked.append([fact.id for fact in evidence])
        return True

    result = ContradictionClassifier(judge).classify(
        nora_claim("Nora stepped closer."),
        comparison(Verdict.ENTAILMENT, supporting=["F040"]),
        [BUILD],
    )
    assert result.classification == ClaimClassification.VALID_NEW_ADDITION
    assert result.evidence_ids == []
    assert asked == [["F040"]]


def test_support_from_a_fact_the_claim_is_about_is_kept():
    result = ContradictionClassifier(must_not_be_called).classify(
        nora_claim("Nora is lean."),
        comparison(Verdict.ENTAILMENT, supporting=["F040"]),
        [BUILD],
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F040"]


def test_only_the_facts_the_claim_is_about_are_cited_as_support():
    result = ContradictionClassifier().classify(
        nora_claim("Nora is a scout."),
        comparison(Verdict.ENTAILMENT, supporting=["F040", "F041"]),
        [BUILD, SCOUT],
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F041"]


def test_a_paraphrase_of_an_exclusive_fact_is_still_support_without_a_shared_word():
    """Status, species and family values are implied by many wordings, so they are not filtered."""
    result = ContradictionClassifier(must_not_be_called).classify(
        nora_claim("Nora is still living."),
        comparison(Verdict.ENTAILMENT, supporting=["F043"]),
        [STILL_ALIVE],
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F043"]


def test_a_slot_fact_cannot_support_a_claim_that_is_not_about_it():
    result = ContradictionClassifier().classify(
        nora_claim("Nora stepped closer."),
        comparison(Verdict.ENTAILMENT, supporting=["F042"]),
        [KATANA],
    )
    assert result.classification != ClaimClassification.SUPPORTED
    assert result.evidence_ids == []


def test_a_dropped_conflict_does_not_fall_back_on_unrelated_support():
    """A rejected conflict used to leave the claim "supported" by whatever else the NLI offered."""
    result = ContradictionClassifier().classify(
        nora_claim("Nora stepped closer."),
        comparison(Verdict.CONTRADICTION, supporting=["F040"], conflicting=["F033"]),
        [BUILD, JOB],
    )
    assert result.classification != ClaimClassification.SUPPORTED
    assert result.evidence_ids == []


def test_the_support_check_can_be_replaced():
    result = ContradictionClassifier(supports_topic=lambda text, fact: True).classify(
        nora_claim("Nora stepped closer."),
        comparison(Verdict.ENTAILMENT, supporting=["F040"]),
        [BUILD],
    )
    assert result.classification == ClaimClassification.SUPPORTED
    assert result.evidence_ids == ["F040"]


def test_the_topic_check_can_be_replaced():
    result = ContradictionClassifier(mentions_topic=lambda text, fact: True).classify(
        kael_claim("Kael brushed moss from the road."),
        comparison(Verdict.CONTRADICTION, conflicting=["F033"]),
        [JOB],
    )
    assert result.classification == ClaimClassification.UNCERTAIN
    assert result.evidence_ids == ["F033"]


def test_the_attribute_check_can_be_replaced():
    result = ContradictionClassifier(refers_to_attribute=lambda text, fact: True).classify(
        kael_claim("Kael had a pack mule."),
        comparison(Verdict.CONTRADICTION, conflicting=["F030"]),
        [HAIR],
    )
    assert result.classification == ClaimClassification.CONTRADICTION
