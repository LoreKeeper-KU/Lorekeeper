# Multimodal Visuals (Owner: Saif)

Turns a verified scene into an illustration, checks the **actual image** against
canon, and repairs it when something is wrong.

```
scene + canon facts
  -> build_visual_prompt()   text prompt for the image model
  -> generate_visual()       image saved to outputs/, returns VisualAsset
  -> verify_visual()         vision model checks every fact, returns VisualReport
  -> repair_visual()         edits mismatches and re-checks (max 3 edits)
```

All AI calls go through the shared `shared/ai_client.py` (plain HTTP,
OpenAI-compatible, so the provider/models can be switched in `.env`).

## Public functions (`multimodal/visuals.py`)

| Function | Returns | What it does |
|---|---|---|
| `generate_visual(scene, canon_facts, ai=None)` | `VisualAsset` | Builds the prompt and generates + saves the image |
| `verify_visual(asset, canon_facts, ai=None)` | `VisualReport` | Checks the image against each fact; `consistent=False` lists issues and the broken `evidence_fact_ids` |
| `repair_visual(asset, report, canon_facts, ai=None, max_attempts=3)` | `VisualRepairResult` | Edits only the mismatched details, re-verifies the new image, stops after `max_attempts` |

`VisualAsset` and `VisualReport` are the shared contracts in `shared/schemas.py`.
`VisualRepairResult` (in `multimodal/models.py`) holds the final `asset`, its
`report`, the number of `attempts`, and `needs_human_review` (True if mismatches
remain after all attempts).

The optional `ai` argument lets tests pass a fake client (no cost). Leave it
out in real use and a real `AIClient` is created.

### Example

```python
from multimodal.visuals import generate_visual, repair_visual, verify_visual
from shared.schemas import CanonFact

facts = [
    CanonFact(id="F001", subject="Princess Amina", predicate="hair_color", object="black"),
    CanonFact(id="F004", subject="Princess Amina", predicate="armor_color", object="silver"),
]

asset = generate_visual("Princess Amina commands archers from the castle walls.", facts)
report = verify_visual(asset, facts)
if not report.consistent:
    result = repair_visual(asset, report, facts)
    asset, report = result.asset, result.report

print(asset.image_path, report.consistent, report.issues)
```

## How verification works

The vision model gives a verdict per fact: `match`, `mismatch` or
`unable_to_assess` (hidden, too small, or not something a picture can show,
such as who rules a kingdom). Only real mismatches make an image inconsistent:

- a hidden detail is never counted as a mismatch (or reported as an issue);
- extra details the facts don't mention are not mismatches;
- a fact id the model invents is ignored.

## Configuration

Set in `.env` (see `.env.example`); read by `shared/config.py`:

| Setting | Default | Used for |
|---|---|---|
| `AI_API_KEY` | (required) | API key, never committed |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Provider address |
| `IMAGE_MODEL` | `gpt-image-2` | Generating and editing images |
| `VISION_MODEL` | `gpt-5.4-mini` | Checking images |
| `IMAGE_SIZE` | `1024x1024` | Image size |

Images are saved to `outputs/` (git-ignored) with unique, time-stamped names.
The art style is the `STYLE` constant in `visuals.py`.

**Reference images:** not supported yet. The planned approach is to pass an
approved character portrait to the image model alongside the prompt, so a
character looks the same across scenes.

## Tests

```
python -m pytest
```
`tests/test_visuals.py` and `tests/test_evaluation.py` use a fake AI client:
free, no API key needed.

## Evaluation

```
python -m multimodal.evaluation run         # paid: runs the 10 scenarios
python -m multimodal.evaluation summarize   # compares the verifier with human verdicts
```

- Scenarios: `multimodal/eval_scenarios.json`: 6 clean and 4 with a
  deliberately injected error (e.g. generated with gold armor while canon says
  silver), plus hidden details (back view) and a non-visual fact.
- Records: `multimodal/eval_results.csv`: one row per fact, with the
  verifier's verdict and the human verdict.

### Results (10 scenarios, 30 facts, human-judged)

| Measure | Result |
|---|---|
| Verifier agreement with human | **90%** (27/30) |
| False alarms (verifier said mismatch, human saw a match) | **0** |
| Missed mismatches (verifier said match, human saw a mismatch) | 2 |
| Claimed to see a non-visual fact | 1 |
| Attribute consistency of first images (human) | 82% (23/28 assessable facts) |
| Injected errors caught by the verifier | 3 of 4 |
| Scenarios repaired / fixed | 3 / 3, one edit each |
| API calls for the whole run | 10 images, 3 edits, 16 vision checks |

**What this shows:** the verifier never invented a problem, so a `mismatch`
verdict can be trusted. Its errors were all in the generous direction (saying
`match` when it shouldn't), so a `consistent` verdict still deserves a human
spot-check. Every detected mistake was fixed with a single edit.

We also found that the image model does not always follow the prompt: in one
scenario it ignored the injected detail. Checking the actual image, rather than
trusting the prompt, is therefore necessary.

## Known limitations / for the team

- `VisualReport` has no field for `unable_to_assess`, so hidden details are
  dropped from the shared report (they are kept internally). Suggestion: add
  `unassessable_fact_ids` to `VisualReport` in `shared/schemas.py`.
- Non-visual facts (e.g. "rules Eldoria") should ideally be filtered out
  before verification; the verifier occasionally claims to see them.
- Reference images are not implemented yet.
