# Authored by Faris
"""Which canon facts rule out other values, so that a conflict with them can count.

A CanonFact is not necessarily exclusive: "weapon=golden spear" does not prove Arin
cannot also carry a silver sword. Only the predicates listed here, plus facts whose
object is an explicit "none", may license a CONTRADICTION. Everything else is
non-exclusive, so an NLI conflict with it stays Uncertain.
"""

import re

from continuity_checker.models import CanonFact
from continuity_checker.relevance import STOPWORDS

# Single-valued attributes and relationships: a subject has one value at a time. Father,
# mother, house and allegiance follow the benchmark's labelling policy (one father, one mother,
# one house, one sworn allegiance); weapon, tool, pet and vehicle stay non-exclusive.
EXCLUSIVE_PREDICATES = frozenset(
    {"status", "eye_color", "hair_color", "species", "birthplace", "father", "mother", "house", "allegiance"}
)

# An explicit absence excludes every claimed value, whatever the predicate.
NEGATIVE_OBJECTS = frozenset({"none", "nobody", "no_one", "nothing", "never"})


# Words that show a claim is talking about an attribute. An NLI model will sometimes report a
# "conflict" between an exclusive fact and a claim about something else entirely ("Kael had a
# mule" against hair_color=black), so a conflict with these facts only counts when the claim
# mentions the attribute. Only the attributes where that was observed are listed: values such as
# status ("the funeral procession passed"), species or family are implied by many wordings no
# cue list could cover, so every other predicate is left as it was.
ATTRIBUTE_CUES = {
    "eye_color": frozenset({"eye", "eyes", "eyed", "iris", "irises"}),
    "hair_color": frozenset(
        {"hair", "haired", "blond", "blonde", "brunette", "redhead", "redheaded", "bald"}
    ),
    "magic_ability": frozenset(
        {
            "magic", "magical", "magically", "mage", "mages", "wizard", "witch", "sorcerer",
            "sorceress", "sorcery", "spell", "spells", "spellcasting", "spellcaster", "cast",
            "casts", "casting", "conjure", "conjures", "conjured", "summon", "summons", "summoned",
            "summoning", "enchant", "enchanted", "enchantment", "incantation", "curse", "cursed",
            "hex", "mystic", "mystical", "arcane", "supernatural", "teleport", "teleported",
        }
    ),
}


# Slots that can hold several values (the benchmark's labelling policy: weapon, tool, pet,
# vehicle). A different value is reported as tension however the claim is worded ("drew a steel
# dagger" never says "weapon"), so these facts are never filtered by topic.
SLOT_PREDICATES = frozenset({"weapon", "tool", "pet", "vehicle"})

# Function words that carry no topic, on top of relevance.STOPWORDS.
_FILLER = STOPWORDS | frozenset(
    "will would can could may might shall should who whom which what when where while than then "
    "there these those into onto over under about after before once also very more most some any "
    "all each every just still again".split()
)


def _key(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", text.strip().lower())


def _topic_words(text: str) -> set[str]:
    """Content words of a text, lower-cased with a plural "s" removed ("maps" matches "map")."""
    words = set()
    for word in re.findall(r"[a-z]+", text.lower()):
        if len(word) > 1 and word not in _FILLER:
            words.add(word[:-1] if len(word) > 3 and word.endswith("s") else word)
    return words


def is_exclusive(
    fact: CanonFact, exclusive_predicates: frozenset[str] = EXCLUSIVE_PREDICATES
) -> bool:
    return _key(fact.predicate) in exclusive_predicates or _key(fact.object) in NEGATIVE_OBJECTS


def refers_to_attribute(
    claim_text: str,
    fact: CanonFact,
    attribute_cues: dict[str, frozenset[str]] = ATTRIBUTE_CUES,
) -> bool:
    """Is the claim about the attribute this fact states? Predicates without cues always are."""
    cues = attribute_cues.get(_key(fact.predicate))
    if cues is None:
        return True
    return not cues.isdisjoint(re.findall(r"[a-z]+", claim_text.lower()))


def mentions_topic(
    claim_text: str,
    fact: CanonFact,
    attribute_cues: dict[str, frozenset[str]] = ATTRIBUTE_CUES,
    slot_predicates: frozenset[str] = SLOT_PREDICATES,
) -> bool:
    """Is the claim about the subject matter of a non-exclusive fact?

    True when the claim shares a content word with the fact's predicate, its value or its cue
    words. The subject's own name never counts: every claim about Kael names Kael. Slot
    predicates are always True (see SLOT_PREDICATES).
    """
    key = _key(fact.predicate)
    if key in slot_predicates:
        return True
    claim_words = _topic_words(claim_text) - _topic_words(fact.subject)
    topic = _topic_words(key.replace("_", " ")) | _topic_words(fact.object)
    for cue in attribute_cues.get(key, ()):
        topic |= _topic_words(cue)
    return not claim_words.isdisjoint(topic)


def supports_topic(
    claim_text: str,
    fact: CanonFact,
    attribute_cues: dict[str, frozenset[str]] = ATTRIBUTE_CUES,
) -> bool:
    """May this non-exclusive fact count as support for the claim?

    Like mentions_topic, but with no slot exemption: a different weapon is tension however the
    claim is worded, yet a weapon fact never supports a claim that does not mention it.
    """
    return mentions_topic(claim_text, fact, attribute_cues, slot_predicates=frozenset())
