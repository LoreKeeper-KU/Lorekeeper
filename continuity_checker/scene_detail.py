# Authored by Faris
"""Which claims are anonymous scenery: weather, terrain, objects, animals, sounds, bystanders.

A claim no canon fact is about may still be a harmless scene detail ("A bird startled from a
nearby pine."). One that names a person or place canon does not contain is a different case:
the frozen labelling policy keeps it Uncertain (`entity_absent`). This check keeps the two
apart deterministically, and errs towards "not scenery": a claim counts only if it opens like
scenery AND uses no capitalised word that is not the start of a sentence. A name at the start
("Zayd defended the city.") does not open like scenery, so it is never one.
"""

import re

# Words that open a claim about the setting rather than about someone: determiners, "there" and
# "it", place words and prepositions, weather and light nouns, and plural or mass nouns for
# things in a scene. A noun is only added if it is not also a common first name ("Ivy", "Ash",
# "Rose", "Hazel" stay out), since a name opening a claim must never count as scenery.
SCENE_OPENERS = frozenset(
    "a an the this that these those there here it its some another every each one two three few many "
    "no any all both most several either neither "
    "someone somebody something anyone anybody anything nobody nothing everyone everybody everything "
    "somewhere nearby far above below behind beyond beneath beside inside outside overhead ahead "
    "in on at across along over under through from "
    "wind rain snow smoke dust mist fog frost thunder silence darkness moonlight sunlight night dusk "
    "light shadows birdsong "
    "moss cracks vines roots branches boughs leaves stones pebbles rocks boulders cobblestones "
    "ravens crows birds bats insects flies moths mud grass reeds weeds thorns brambles puddles "
    "ripples waves embers sparks ashes flames steam clouds stars echoes footprints tracks "
    "planks beams timbers ropes chains bells torches lanterns candles crates barrels wagons carts "
    "tents doors windows walls floors rooftops chimneys cobwebs scraps debris rubble".split()
)

_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
_SENTENCE_STARTS = ('.', '?', '!', '"', '“', '‘', "'", '(')


def _names_an_entity(text: str) -> bool:
    """A capitalised word that does not begin a sentence or a quotation ("I" aside)."""
    for match in list(_WORD.finditer(text))[1:]:
        before = text[: match.start()].rstrip()
        if before and before[-1] in _SENTENCE_STARTS:
            continue
        word = match.group()
        if word[0].isupper() and word != "I":
            return True
    return False


def is_scene_detail(claim_text: str, openers: frozenset[str] = SCENE_OPENERS) -> bool:
    text = claim_text.strip()
    first = re.match(r"\W*([A-Za-z]+)", text)
    if first is None or first.group(1).lower() not in openers:
        return False
    return not _names_an_entity(text)
