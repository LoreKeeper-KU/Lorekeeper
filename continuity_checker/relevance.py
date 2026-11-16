# Authored by Faris
"""Pick the canon facts worth comparing with a claim.

A fact is relevant when the claim shares at least one content word with the fact's
subject or object (the entities). The predicate is ignored: it is a generic relation
word such as "rules", shared by unrelated facts. Recall is favoured over precision, so
titles like "queen" still match, and one shared word is enough.
"""

import re

from continuity_checker.models import CanonFact, Claim

STOPWORDS = frozenset(
    "a an the of in on at to and or but is was were be been it its he him his she her "
    "they them their with for from by as that this had has have not".split()
)


def _words(text: str) -> set[str]:
    text = re.sub(r"['’]s\b", "", text.lower())
    return set(re.findall(r"[a-z0-9]+", text)) - STOPWORDS


def select_relevant_facts(claim: Claim, canon_evidence: list[CanonFact]) -> list[CanonFact]:
    claim_words = _words(claim.text)
    return [
        fact
        for fact in canon_evidence
        if claim_words & (_words(fact.subject) | _words(fact.object))
    ]
