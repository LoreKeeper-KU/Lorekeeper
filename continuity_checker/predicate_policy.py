# Authored by Faris
"""Which canon facts rule out other values, so that a conflict with them can count.

A CanonFact is not necessarily exclusive: "weapon=golden spear" does not prove Arin
cannot also carry a silver sword. Only the predicates listed here, plus facts whose
object is an explicit "none", may license a CONTRADICTION. Everything else is
non-exclusive, so an NLI conflict with it stays Uncertain.
"""

import re

from continuity_checker.models import CanonFact

# Single-valued attributes and relationships: a subject has one value at a time. Father,
# mother, house and allegiance follow the benchmark's labelling policy (one father, one mother,
# one house, one sworn allegiance); weapon, tool, pet and vehicle stay non-exclusive.
EXCLUSIVE_PREDICATES = frozenset(
    {"status", "eye_color", "hair_color", "species", "birthplace", "father", "mother", "house", "allegiance"}
)

# An explicit absence excludes every claimed value, whatever the predicate.
NEGATIVE_OBJECTS = frozenset({"none", "nobody", "no_one", "nothing", "never"})


def _key(text: str) -> str:
    return re.sub(r"[\s\-]+", "_", text.strip().lower())


def is_exclusive(
    fact: CanonFact, exclusive_predicates: frozenset[str] = EXCLUSIVE_PREDICATES
) -> bool:
    return _key(fact.predicate) in exclusive_predicates or _key(fact.object) in NEGATIVE_OBJECTS
