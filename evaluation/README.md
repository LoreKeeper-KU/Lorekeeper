# Continuity Verification: Evaluation Summary

This folder holds the evaluation of the continuity-verification module (Faris): the part of
LoreKeeper that compares an atomic claim from a generated scene with canon facts and classifies
it as **SUPPORTED**, **CONTRADICTION**, **VALID_NEW_ADDITION** or **UNCERTAIN**.

## What was measured

Whether the verifier assigns the correct one of the four classes to a manually labelled claim,
given the canon facts of its fictional world. Metrics: accuracy, per-class precision / recall /
F1, macro-F1, the confusion matrix, **unsafe approvals** (a claim that canon contradicts or cannot
settle, offered as a Valid New Addition), **false contradictions**, and whether SUPPORTED and
CONTRADICTION claims cite exactly the right canon fact IDs.

**Claim extraction was excluded.** Every record is already one atomic claim and is fed to the
pipeline as written, after the extraction stage. The evaluation therefore measures continuity
verification only: relevance filtering, NLI comparison, the exclusivity policy, the
AdditionJudge and the final classification.

## Datasets

All three use the same labelling policy (`benchmark/LABELLING_POLICY.md`), different fictional
worlds, and a hash manifest (`MANIFEST.json`) that freezes the labels before a run. A test fails
if any claim, fact ID or entity name is shared between them.

| Set | Claims | Folder | Purpose |
|---|---|---|---|
| Frozen benchmark | 52 | `benchmark/` | Baseline measurement, before any fix |
| Development set | 30 | `devset/` | Experimenting with fixes and checking for regressions |
| Final held-out set | 32 | `heldout/` | One final, untuned measurement (8 claims per class) |

## Results

| Set | When | Accuracy | Macro-F1 |
|---|---|---|---|
| Benchmark (baseline) | Before any fix | **80.8%** (42/52) | **0.816** |
| Dev set | Before fixes | 63.3% (19/30) | 0.680 |
| Dev set | After the relationship-exclusivity fix | 86.7% (26/30) | 0.844 |
| Dev set | After the AdditionJudge rule clarification | **96.7%** (29/30) | **0.964** |
| **Final held-out** | After all fixes, run once | **93.8%** (30/32) | **0.939** |

The dev-set figures are a **tuning and regression result**, not a generalization score: the fixes
were designed after seeing the failures on those claims. The benchmark baseline was not rerun
after the fixes. The final held-out figure is the generalization estimate.

### Final held-out result

| Class | Precision | Recall | F1 |
|---|---|---|---|
| SUPPORTED | 1.000 | 0.875 | 0.933 |
| CONTRADICTION | 1.000 | 0.875 | 0.933 |
| VALID_NEW_ADDITION | 0.800 | 1.000 | 0.889 |
| UNCERTAIN | 1.000 | 1.000 | 1.000 |

- **Evidence exact-match:** 100% (14 of 14 correctly classified SUPPORTED and CONTRADICTION claims).
- **False contradictions:** 0.
- **Unsafe approvals:** 1.
- **Judge calls:** 14.

Two claims were wrong:

1. **H1-02, a hard paraphrase.** "Research centres on stars whose brightness varies" restates the
   canon fact "specialty: variable stars". The NLI model scored it neutral, so no supporting fact
   was found, and the claim was offered as a new addition.
2. **H3-04, an implicit contradiction.** "Fenn Hadley counted the day's rum casks at dawn" implies
   he is alive, but canon says he is dead. The NLI model scored it neutral and the AdditionJudge,
   although shown the status fact, approved it. This is the one unsafe approval.

## Main improvements made during the evaluation

- **Relationship exclusivity.** The first benchmark run showed that correct NLI contradictions
  with father, mother, house and allegiance facts were being downgraded to UNCERTAIN. These four
  predicates were added to the exclusivity policy, in line with the labelling policy (one father,
  one mother, one house, one sworn allegiance). A shared-word guard was tried on paper and
  rejected, because a replay on the dev set showed it would lose four true contradictions.
- **AdditionJudge rules.** The judge flipped verdicts between identical runs on thin-context
  claims and superlatives. Its prompt now states that few canon facts alone is not a reason to
  decline, that a harmless event, interaction or background detail can be a valid addition, and
  that unsettled core attributes or relationships, world-rule changes and unestablished
  superlatives such as "best", "greatest", "largest", "only" or "first" are insufficient context.

## Limitations

- **Small datasets.** The held-out set has 32 claims (8 per class), so one claim moves overall
  accuracy by about 3 points. A 95% interval on 30/32 is roughly 80% to 98%.
- **The AdditionJudge is nondeterministic.** The shared AI client does not pin the temperature, so
  the same claim can receive different verdicts on different runs. Each set was run once per
  configuration, so run-to-run variance was not measured.
- **The final held-out set was run once and not tuned afterward.** Its result should be read as
  final.
- **One author.** All claims and labels were written by the module author, and the sets were
  written to include known weak spots, so they are not a neutral sample. A second labeller has
  not checked them.
- **Scope.** Claim extraction quality, story-time facts and retrieval quality are not evaluated.
  Only predicates on a small exclusivity list can produce a CONTRADICTION.

## Reproduce

```bash
python -m evaluation.runner --set benchmark   # frozen benchmark -> results/
python -m evaluation.runner --set dev         # dev set          -> results_dev/
python -m evaluation.runner --set heldout     # held-out set     -> results_heldout/
```

Each run needs the NLI model (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`), an `AI_API_KEY` for
the AdditionJudge, and a dataset whose manifest still verifies. Each run writes
`predictions.csv`, `metrics.json`, `failures.jsonl` and `run_info.json` (models, thresholds,
prompt hash, git commit) to its own folder. The held-out set is meant to be run once.

Result folders: `results/20261108-130756` (baseline), `results_dev/20261113-101102`,
`results_dev/20261113-101548`, `results_dev/20261113-105149` (dev runs), and
`results_heldout/20261113-110427` (final).
