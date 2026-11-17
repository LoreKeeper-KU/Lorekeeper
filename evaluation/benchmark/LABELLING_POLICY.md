# Labelling policy for the continuity benchmark

These rules were written, and every label assigned, **before the verifier was run on any
benchmark claim**. Labels follow the project policy below, not the behaviour of the NLI model,
the exclusivity list, or the AdditionJudge. When the verifier disagrees with a label, the
verifier is wrong by definition. Do not change a label after seeing a result; the dataset is
frozen by `MANIFEST.json`.

## Input

Each record is one manually defined **atomic claim**. It is given to the verifier directly,
after the extraction stage, so extraction quality is not measured. Each claim is checked against
all facts of its world (5 to 8 CanonFact triples). The relevance filter, NLI comparison,
exclusivity policy, AdditionJudge and final classification are all exercised.

## The four classes

**SUPPORTED.** A canon fact states or directly entails the claim, including a paraphrase or an
absence stated in words (for example `magic_ability: none` supports "cannot cast spells").
`expected_evidence_ids` lists the supporting fact(s).

**CONTRADICTION.** A canon fact makes the claim impossible. This holds when the claim gives a
different value for an attribute that is **single-valued**, or does something canon rules out.
Single-valued attributes in this benchmark: status (alive/dead), species, birthplace, eye and
hair colour, father, mother, a school house, and a sworn allegiance. An explicit `none`
(no ability, no skill, no training) rules out every claimed instance. `expected_evidence_ids`
lists the conflicting fact(s).

**UNCERTAIN.** The claim cannot be accepted or rejected safely. Four kinds:
- `non_exclusive`: the claim gives a different value for a slot that can hold several values
  (weapon, tool, pet, vehicle). The canon value does not rule it out, and does not support it.
- `core_unsettled`: the claim concerns a core attribute (family, status, species, abilities,
  allegiance) that the shown facts do not settle (for example a sibling or a child).
- `entity_absent`: the claim is about a person or place that appears nowhere in canon.
- `partial`: the claim restates a canon fact but adds an unestablished qualifier such as
  "the only", "the largest" or "the best".

**VALID_NEW_ADDITION.** A concrete new detail, event or interaction that canon does not state,
that conflicts with no shown fact (even by implication), that concerns established characters or
places, and that changes no core attribute or world rule. It is only a candidate for user
approval, never new canon. Kinds: `event`, `interaction`, `background`.

Missing evidence alone never makes a claim VALID_NEW_ADDITION: entity_absent claims are
UNCERTAIN even though no fact contradicts them.

## Assumptions and exclusions

- **Father, mother, house and allegiance are treated as single-valued, core relationships for
  this benchmark.** A character has one father, one mother, one school house and one sworn
  allegiance, so a claim naming a different value contradicts canon. This is a deliberate
  simplification: it ignores adoptive or step parents, double agents and changes of loyalty.
  Facts about these relationships are core attributes, so a new relative or allegiance that
  canon does not mention is UNCERTAIN, not a VALID_NEW_ADDITION.
- No fact in the benchmark changes over story time; claims about "before" or "after" a canon
  fact are not included.
- Claim wording is natural prose, not the triple form, and several claims paraphrase canon.
- The labels are one person's reading of the policy. A second reader should check a sample, and
  the categories `partial` and `non_exclusive` are the most subjective.
