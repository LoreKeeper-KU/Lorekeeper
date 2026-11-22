# Authored by Faris
"""Canon and fakes shared by the false-flag regression tests.

The facts have the shape the integrated app now feeds the verifier: character-creator canon
(a `name` fact, long prose core fields, short attributes such as `hair_color` and
`magic_ability: none`) with the character's readable name as the subject, which is what
`readable_canon()` produces. Kael and Mira are reconstructed from a bug report; King Arthur's
facts are copied from a real saved character.

ScriptedNLI reproduces what the real DeBERTa model was observed to answer (see OBSERVED_NLI),
so the fast tests are deterministic. test_false_flag_real_model.py runs the same cases against
the real model.
"""

from continuity_checker.canon_verifier import CanonVerifier, Verdict
from continuity_checker.contradiction_classifier import ContradictionClassifier
from continuity_checker.models import CanonFact, Claim, ClaimClassification, SourceSpan


def character(key, name, attributes):
    """A `name` fact plus one fact per (predicate, object); IDs look like `kael-hair-color`."""
    facts = [CanonFact(id=f"{key}-name", subject=name, predicate="name", object=name)]
    for predicate, value in attributes:
        facts.append(
            CanonFact(
                id=f"{key}-{predicate.replace('_', '-')}",
                subject=name,
                predicate=predicate,
                object=value,
            )
        )
    return facts


KAEL = character("kael", "Kael", [
    ("role", "Wandering cartographer"),
    ("appearance", "A lean traveler with windburned cheeks, short black hair and a patched green "
                   "coat, carrying rolled maps in a leather tube."),
    ("background", "Kael left a river guild to chart the unmapped forest passes, selling his maps "
                   "to villages along the old roads."),
    ("goal", "To finish a complete map of the northern passes and bring it home."),
    ("flaw", "He is stubborn about his own measurements and will not turn back once a route is "
             "chosen."),
    ("hair_color", "black"),
    ("eye_color", "green"),
    ("magic_ability", "none"),
    ("occupation", "cartographer"),
])

MIRA = character("mira", "Mira", [
    ("role", "Thief"),
    ("appearance", "A quick, narrow-faced woman with black hair, dark clothes and ink-stained "
                   "fingers."),
    ("background", "Mira grew up in the lower districts, learning locks before letters."),
    ("goal", "To steal the vault key."),
    ("flaw", "She cannot resist a dare, even a foolish one."),
    ("hair_color", "black"),
    ("magic_ability", "none"),
    ("occupation", "thief"),
])

ARTHUR = character("arthur", "king arthur", [
    ("role", "Legendary king and unifier of a fractured realm"),
    ("appearance", "A broad-shouldered nobleman with weathered features, dark hair kept short "
                   "beneath a gilded crown, and a scarred hand from years of war. He favors "
                   "practical armor under a regal cloak, blending battlefield readiness with "
                   "royal authority."),
    ("background", "Born into uncertainty and raised among courtly intrigue, Arthur earned the "
                   "throne through a test of legitimacy that revealed his right to rule. He came "
                   "of age during a time of rival lords and broken alliances, and built his "
                   "reputation by uniting competing factions through courage, diplomacy, and the "
                   "loyalty of gifted knights."),
    ("goal", "To forge a lasting kingdom built on justice, unity, and honor, and to protect it "
             "from internal betrayal and external threats."),
    ("flaw", "He trusts ideals more readily than people, which can leave him vulnerable to "
             "deception and to the burden of impossible expectations."),
    ("hair_color", "black"),
    ("eye_color", "gray"),
    ("stance", "upright and commanding"),
    ("weapon", "enchanted sword"),
    ("armor_style", "plate armor with royal heraldry"),
    ("leadership_style", "noble and principled"),
    ("magic_ability", "minor mystical protection"),
])

NORA = character("nora", "Nora", [
    ("role", "Scout"),
    ("appearance", "A lean, quick-footed woman with cropped dark hair and a weathered green cloak."),
    ("background", "Nora grew up guiding caravans through the salt flats."),
    ("goal", "To find her missing brother."),
    ("flaw", "She trusts her instincts over any plan."),
    ("build", "lean"),
    ("occupation", "scout"),
    ("height", "average"),
    ("stance", "alert"),
    ("hair_color", "dark brown"),
    ("eye_color", "hazel"),
])

# A status fact that "is still living" restates without sharing a single word with it.
SHEIKH = [CanonFact(id="sheikh-status", subject="Sheikh Idris", predicate="status", object="alive")]

# A non-exclusive slot: a golden spear does not rule out a silver sword.
ARIN = [CanonFact(id="arin-weapon", subject="Arin", predicate="weapon", object="golden spear")]

ALL_CHARACTERS = KAEL + MIRA + ARTHUR

# The (claim -> fact IDs the NLI model calls CONTRADICTION) answers observed from the real
# DeBERTa model on 2026-11-22. The first group is the model being wrong about unrelated
# claims; the second group is it being right. Everything not listed is NEUTRAL.
OBSERVED_NLI = {
    # false conflicts
    "Kael had a pack mule.": {"kael-flaw", "kael-hair-color", "kael-eye-color", "kael-magic-ability"},
    "Kael had a mule.": {"kael-hair-color", "kael-eye-color", "kael-magic-ability"},
    "Kael brushed moss from the road.": {"kael-occupation"},
    "Kael led the mule forward.": {"kael-role", "kael-background", "kael-occupation"},
    "Mira stopped at once.": {
        "mira-name", "mira-role", "mira-goal", "mira-flaw", "mira-magic-ability", "mira-occupation",
    },
    "King Arthur said 'Enough.'": {"arthur-goal", "arthur-flaw", "arthur-magic-ability"},
    "Nora stepped closer.": {"nora-stance"},
    "Nora ran.": {"nora-name", "nora-background", "nora-build", "nora-occupation", "nora-stance"},
    # real conflicts
    "Kael has blue eyes.": {"kael-eye-color"},
    "Kael has red hair.": {"kael-hair-color"},
    "Kael cast a fire spell.": {"kael-magic-ability"},
    "Arin drew a silver sword.": {"arin-weapon"},
}


# The (claim -> fact IDs the NLI model calls ENTAILMENT) answers observed from the same DeBERTa
# model while diagnosing false SUPPORT. The first group is the model "supporting" plain actions
# with facts that are not about them; the second group is it correctly supporting claims that
# restate a fact.
OBSERVED_ENTAILMENTS = {
    # false support
    "Nora stepped closer.": {"nora-build"},
    "Nora ran.": {"nora-appearance"},
    "Kael ran.": {"kael-flaw"},
    "Kael followed the path.": {"kael-flaw", "kael-background"},
    "King Arthur ran.": {"arthur-role", "arthur-leadership-style"},
    "King Arthur followed the path.": {"arthur-background"},
    # real support
    "Nora is lean.": {"nora-appearance", "nora-build"},
    "Nora has hazel eyes.": {"nora-eye-color"},
    "Nora is a scout.": {"nora-role", "nora-occupation"},
    "Sheikh Idris is still living.": {"sheikh-status"},
}


class ScriptedNLI:
    """A Comparator that answers only for the pairs it is told about; everything else is NEUTRAL.

    A pair listed as both contradiction and entailment is a contradiction, as in compare_claim.
    """

    def __init__(self, contradictions=None, entailments=None):
        self.contradictions = OBSERVED_NLI if contradictions is None else contradictions
        self.entailments = OBSERVED_ENTAILMENTS if entailments is None else entailments

    def __call__(self, claim, fact):
        if fact.id in self.contradictions.get(claim.text, ()):
            return Verdict.CONTRADICTION
        if fact.id in self.entailments.get(claim.text, ()):
            return Verdict.ENTAILMENT
        return Verdict.NEUTRAL


class SpyJudge:
    """An AdditionJudge that records what it was asked and answers with a fixed decision."""

    def __init__(self, approves):
        self.approves = approves
        self.calls = []  # (claim text, IDs of the facts shown)

    def __call__(self, claim, canon_evidence):
        self.calls.append((claim.text, [fact.id for fact in canon_evidence]))
        return self.approves


def classify(text, facts, comparator, judge):
    """Run one claim through the real relevance filter, comparison and classifier."""
    verifier = CanonVerifier(
        extractor=None,
        comparator=comparator,
        classifier=ContradictionClassifier(addition_judge=judge),
    )
    claim = Claim(claim_id="C001", text=text, source_span=SourceSpan(start=0, end=len(text)))
    return verifier.verify_claim(claim, facts)


CONTRADICTION = ClaimClassification.CONTRADICTION
SUPPORTED = ClaimClassification.SUPPORTED
UNCERTAIN = ClaimClassification.UNCERTAIN
VALID_NEW_ADDITION = ClaimClassification.VALID_NEW_ADDITION
