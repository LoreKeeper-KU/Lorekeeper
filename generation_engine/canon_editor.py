"""Turn explicit author instructions into reviewable, world-scoped proposals."""

import re
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from canon_memory.canon_store import CanonStore
from shared.schemas import CanonFact
from continuity_checker.predicate_policy import is_exclusive
from .models import PendingCanon


class FactChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    predicate: str = Field(pattern=r"^[a-z][a-z0-9_]*$", description="Reuse existing predicate names. Use former_name for a former identity, alias for an alternative name, and name for the primary name.")
    object: str = Field(min_length=1)
    replaces_fact_id: str = ""


class FactChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[FactChange] = Field(default_factory=list)
    question: str = ""


def prepare_fact_changes(context, world_id, result: FactChanges):
    """Validate tool arguments against current canon before storing proposals."""
    store = CanonStore()
    canon = store.get_facts_by_world(world_id)
    if not result.changes:
        return None, result.question.strip() or "What would you like to establish about this character?"
    by_id = {f.id: f for f in canon}
    subjects = {f.subject for f in canon}
    names = {f.subject: f.object for f in canon if f.predicate == "name"}
    prepared = []
    replaced = set()
    author_text = " ".join([
        context.get("message", ""),
        context.get("conversation_state", {}).get("original_request", ""),
        *(turn["content"] for turn in context.get("history", []) if turn.get("role") == "user"),
    ])
    author_words = set(re.findall(r"\w+", author_text.casefold()))
    for change in result.changes:
        old = by_id.get(change.replaces_fact_id)
        if change.subject not in subjects or (change.replaces_fact_id and (
            old is None or old.subject != change.subject or old.predicate != change.predicate
        )):
            return None, "Which saved character and fact should I change?"
        value = change.object.strip()
        if not value:
            return None, "What should the new fact say?"
        if old is None:
            exclusive = [f for f in canon if f.subject == change.subject
                         and f.predicate == change.predicate and is_exclusive(f)]
            if len(exclusive) > 1:
                return None, "There are multiple saved values for that attribute. Which fact should I replace?"
            if exclusive:
                old = exclusive[0]
        if old and old.id in replaced:
            return None, "You supplied different edits to the same fact. Which value should I use?"
        if old:
            replaced.add(old.id)
        if any(f.subject == change.subject and f.predicate == change.predicate
               and f.object.casefold() == value.casefold() for f in canon):
            continue
        fact = CanonFact(id=old.id if old else uuid4().hex,
                         subject=change.subject, predicate=change.predicate, object=value)
        if is_exclusive(fact):
            value_words = set(re.findall(r"\w+", value.casefold())) - {"a", "an", "the", "and"}
            explicit_absence = value.casefold() == "none" and bool(author_words & {"no", "without", "cannot", "none"})
            if not value_words.issubset(author_words) and not explicit_absence:
                attribute = fact.predicate.replace("_", " ")
                return None, f"What {attribute} should {names.get(fact.subject, fact.subject)} have?"
        if not any((f.subject, f.predicate, f.object) == (fact.subject, fact.predicate, fact.object)
                   for f, _ in prepared):
            prepared.append((fact, old))
    if not prepared:
        return None, "Those facts are already saved in canon."
    ids = [store.propose_revision(world_id, f) if old else store.propose_update(world_id, f)
           for f, old in prepared]
    facts = [f for f, _ in prepared]
    pending = PendingCanon(world_id, ", ".join(sorted({names.get(f.subject, f.subject) for f in facts})), facts, ids)
    lines = []
    for fact, old in prepared:
        value = f"{old.object} → {fact.object}" if old else fact.object
        lines.append(f"- {names.get(fact.subject, fact.subject)} — {fact.predicate.replace('_', ' ')}: {value}")
    return pending, "\n".join(lines)
