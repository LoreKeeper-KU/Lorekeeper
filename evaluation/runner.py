"""Run the frozen benchmark through the continuity-verification pipeline and save the results.

Claim extraction is excluded on purpose: every benchmark record is already one atomic claim, so
it is fed straight into CanonVerifier.verify_claim(), which runs the relevance filter, the NLI
comparison, the exclusivity policy, the AdditionJudge and the final classification.

Run it with:  python -m evaluation.runner   (needs a frozen dataset, the NLI model and AI_API_KEY)
"""

import csv
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Optional

from continuity_checker.addition_judge import ADDITION_SYSTEM_PROMPT, LLMAdditionJudge
from continuity_checker.canon_verifier import CanonVerifier
from continuity_checker.contradiction_classifier import ContradictionClassifier
from continuity_checker.models import Claim, SourceSpan
from continuity_checker.nli_comparator import NLIComparator
from continuity_checker.predicate_policy import EXCLUSIVE_PREDICATES, NEGATIVE_OBJECTS
from continuity_checker.relevance import select_relevant_facts
from evaluation.dataset import BENCHMARK_DIR, Benchmark, load_benchmark, verify_manifest
from evaluation.metrics import compute_metrics, evidence_metrics
from shared import config

DEFAULT_NLI_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
RESULTS_DIR = Path(__file__).parent / "results"
REPO_ROOT = Path(__file__).resolve().parent.parent

PREDICTION_COLUMNS = [
    "claim_id", "world_id", "claim", "category", "difficulty", "expected", "predicted", "correct",
    "expected_evidence_ids", "predicted_evidence_ids", "evidence_correct", "relevant_fact_ids",
    "judge_consulted", "judge_verdict", "judge_reasoning", "explanation", "nli",
]  # fmt: skip


class ExtractionDisabled:
    """Stands where the claim extractor would be, and refuses to run."""

    def extract(self, scene):
        raise RuntimeError("claim extraction is excluded from the benchmark")


class Trace:
    """What the pipeline did for the current claim (relevance, NLI scores, judge decision)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.relevant_fact_ids = []
        self.nli = []
        self.judge = []


class _TracingClient:
    """Wraps the judge's client to keep its verdict and reasoning for the report."""

    def __init__(self, client, trace):
        self.client = client
        self.trace = trace

    def generate_structured(self, instructions, prompt, schema):
        decision = self.client.generate_structured(instructions, prompt, schema)
        self.trace.judge.append(decision)
        return decision


def build_verifier(scorer, labels, client, trace: Trace) -> CanonVerifier:
    """The production pipeline, wrapped only to record what it did. Policy is untouched."""

    def traced_scorer(premise, hypothesis):
        probabilities = scorer(premise, hypothesis)
        trace.nli.append(
            {
                "premise": premise,
                "probabilities": {
                    label.lower(): float(p) for label, p in zip(labels, probabilities)
                },
            }
        )
        return probabilities

    def traced_relevance(claim, facts):
        relevant = select_relevant_facts(claim, facts)
        trace.relevant_fact_ids = [fact.id for fact in relevant]
        return relevant

    return CanonVerifier(
        extractor=ExtractionDisabled(),
        comparator=NLIComparator(traced_scorer, labels),
        classifier=ContradictionClassifier(LLMAdditionJudge(_TracingClient(client, trace))),
        relevance=traced_relevance,
    )


def run_benchmark(benchmark: Benchmark, verifier: CanonVerifier, trace: Trace) -> list[dict]:
    records = []
    for item in benchmark.claims:
        trace.reset()
        # The span is a placeholder: the benchmark does not use source positions.
        claim = Claim(
            claim_id=item.claim_id,
            text=item.claim,
            source_span=SourceSpan(start=0, end=len(item.claim)),
        )
        verified = verifier.verify_claim(claim, benchmark.worlds[item.world_id])

        expected = item.expected_classification.value
        predicted = verified.classification.value
        needs_evidence = expected in ("SUPPORTED", "CONTRADICTION") and predicted == expected
        judge = trace.judge[-1] if trace.judge else None
        records.append(
            {
                "claim_id": item.claim_id,
                "world_id": item.world_id,
                "claim": item.claim,
                "category": item.category,
                "difficulty": item.difficulty,
                "expected": expected,
                "predicted": predicted,
                "correct": expected == predicted,
                "expected_evidence_ids": item.expected_evidence_ids,
                "predicted_evidence_ids": verified.evidence_ids,
                "evidence_correct": (
                    set(verified.evidence_ids) == set(item.expected_evidence_ids)
                    if needs_evidence
                    else None
                ),
                "relevant_fact_ids": trace.relevant_fact_ids,
                "judge_consulted": judge is not None,
                "judge_verdict": judge.verdict.value if judge else None,
                "judge_reasoning": judge.reasoning if judge else None,
                "explanation": verified.explanation,
                "nli": trace.nli,
            }
        )
    return records


def build_failures(records: list[dict]) -> list[dict]:
    failures = []
    for record in records:
        if not record["correct"]:
            failure_type = "wrong_class"
        elif record["evidence_correct"] is False:
            failure_type = "wrong_evidence"
        else:
            continue
        failures.append({"failure_type": failure_type, **record})
    return failures


def write_results(output_dir: Path, records: list[dict], run_info: dict) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREDICTION_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    key: json.dumps(value) if isinstance(value, (list, dict)) else value
                    for key, value in record.items()
                }
            )

    metrics = {
        "metrics": compute_metrics(
            [r["expected"] for r in records], [r["predicted"] for r in records]
        ),
        "evidence": evidence_metrics(
            [
                {
                    "expected": r["expected"],
                    "predicted": r["predicted"],
                    "expected_evidence_ids": r["expected_evidence_ids"],
                    "predicted_evidence_ids": r["predicted_evidence_ids"],
                }
                for r in records
            ]
        ),
    }
    _write_json(output_dir / "metrics.json", metrics)

    failures = build_failures(records)
    (output_dir / "failures.jsonl").write_text(
        "".join(json.dumps(failure, ensure_ascii=False) + "\n" for failure in failures),
        encoding="utf-8",
    )
    _write_json(output_dir / "run_info.json", run_info)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _git(*args: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _version(package: str) -> Optional[str]:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def collect_run_info(manifest: dict, verifier: CanonVerifier, nli_model: str) -> dict:
    """Everything needed to reproduce the run. Never includes the API key."""
    status = _git("status", "--porcelain")
    return {
        "run_started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": manifest,
        "nli_model": nli_model,
        "nli_thresholds": {
            "contradiction": verifier.comparator.contradiction_threshold,
            "entailment": verifier.comparator.entailment_threshold,
        },
        "text_model": config.TEXT_MODEL,
        "ai_base_url": config.AI_BASE_URL,
        "judge_prompt_sha256": hashlib.sha256(ADDITION_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "exclusive_predicates": sorted(EXCLUSIVE_PREDICATES),
        "negative_objects": sorted(NEGATIVE_OBJECTS),
        "claim_extraction": "excluded: benchmark claims are fed to the pipeline as written",
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "python": platform.python_version(),
        "packages": {name: _version(name) for name in ("torch", "transformers", "scikit-learn")},
    }


def run_evaluation(
    benchmark_dir: Path, output_root: Path, scorer, labels, client, nli_model: str
) -> Path:
    """Verify the frozen dataset, run it, and write a timestamped results folder."""
    manifest = verify_manifest(benchmark_dir)  # refuses an unfrozen or edited dataset
    benchmark = load_benchmark(benchmark_dir)

    trace = Trace()
    verifier = build_verifier(scorer, labels, client, trace)
    run_info = collect_run_info(manifest, verifier, nli_model)
    records = run_benchmark(benchmark, verifier, trace)

    run_dir = Path(output_root) / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    write_results(run_dir, records, run_info)
    return run_dir


def main() -> None:
    from continuity_checker.nli_comparator import load_hf_scorer
    from shared.ai_client import AIClient

    client = AIClient()  # fails clearly if AI_API_KEY is missing, before the model loads
    scorer, labels = load_hf_scorer(DEFAULT_NLI_MODEL)
    run_dir = run_evaluation(
        BENCHMARK_DIR, RESULTS_DIR, scorer, labels, client, nli_model=DEFAULT_NLI_MODEL
    )
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))["metrics"]
    print(f"results: {run_dir}")
    print(f"accuracy {metrics['accuracy']:.3f}  macro-F1 {metrics['macro_f1']:.3f}")


if __name__ == "__main__":
    main()
