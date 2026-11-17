# Labelling policy for the development set

The development set is labelled with exactly the same policy as the frozen benchmark:
`evaluation/benchmark/LABELLING_POLICY.md` (sha256 `17a9fa9ec8b4c522a130dadbe6292790d8f88bb866812b53846efbb2900e37fb`, recorded in
`evaluation/benchmark/MANIFEST.json`). No rule is added or changed here.

The development set exists for experimenting with fixes. It is kept apart from the frozen
benchmark: different worlds, characters, fact IDs and claims, its own manifest, and results
written to `evaluation/results_dev/`, never to `evaluation/results/`.

Its labels are frozen by `MANIFEST.json` before any experiment, so labels cannot drift toward
the code. Each claim's `category` is a focus tag (for example `relation_unnamed`,
`same_entity_event`, `thin_context`), not a class.
