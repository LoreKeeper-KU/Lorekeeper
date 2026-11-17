# Labelling policy for the held-out set

The held-out set is labelled with exactly the same policy as the frozen benchmark:
`evaluation/benchmark/LABELLING_POLICY.md` (sha256 `17a9fa9ec8b4c522a130dadbe6292790d8f88bb866812b53846efbb2900e37fb`, recorded in
`evaluation/benchmark/MANIFEST.json`). No rule is added or changed here.

The held-out set is for one final performance measurement. It must not be used to tune the
verifier, the prompts, the thresholds or the policy. Its worlds, characters, fact IDs and claims
are all different from the frozen benchmark and the development set, and it has its own manifest.
Results are written to `evaluation/results_heldout/`, never to the other results folders.

Its labels are frozen by `MANIFEST.json` before the measurement. Each claim's `category` is a
focus tag (for example `relation_unnamed`, `thin_context`, `core_unsettled`), not a class.
