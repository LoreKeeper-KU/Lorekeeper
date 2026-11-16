# Authored by Faris
"""The benchmark runner, with a scripted NLI scorer and a fake judge client: no model, no API."""

import csv
import hashlib
import json

import pytest

from continuity_checker.addition_judge import (
    ADDITION_SYSTEM_PROMPT,
    AdditionDecision,
    AdditionVerdict,
)
from continuity_checker.predicate_policy import EXCLUSIVE_PREDICATES
from evaluation.dataset import (
    Benchmark,
    BenchmarkClaim,
    DatasetModifiedError,
    DatasetNotFrozenError,
    write_manifest,
)
from evaluation.runner import (
    Trace,
    build_failures,
    build_verifier,
    collect_run_info,
    run_benchmark,
    run_evaluation,
    write_results,
)
from shared import config
from shared.schemas import CanonFact

LABELS = ["entailment", "neutral", "contradiction"]
ENTAIL, NEUTRAL, CONTRA = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]

FACTS = [
    CanonFact(id="t-001", subject="Ada", predicate="status", object="alive"),
    CanonFact(id="t-002", subject="Ada", predicate="species", object="human"),
]


def make_claim(claim_id, text, expected, evidence=()):
    return BenchmarkClaim(
        claim_id=claim_id,
        world_id="W1",
        claim=text,
        expected_classification=expected,
        expected_evidence_ids=list(evidence),
        category="test",
        difficulty="easy",
        rationale="test",
    )


CLAIMS = [
    make_claim("W1-01", "Ada is alive.", "SUPPORTED", ["t-001"]),
    make_claim("W1-02", "Ada is dead.", "CONTRADICTION", ["t-001"]),
    make_claim("W1-03", "Ada visited the market.", "VALID_NEW_ADDITION"),
    make_claim("W1-04", "Ada owns a lighthouse.", "UNCERTAIN"),
]
BENCHMARK = Benchmark(worlds={"W1": FACTS}, claims=CLAIMS)


class ScriptedScorer:
    """Returns scripted probabilities per (premise, hypothesis); neutral otherwise."""

    def __init__(self):
        self.calls = []
        self.script = {
            ("Ada status: alive", "Ada is alive."): ENTAIL,
            ("Ada status: alive", "Ada is dead."): CONTRA,
        }

    def __call__(self, premise, hypothesis):
        self.calls.append((premise, hypothesis))
        return self.script.get((premise, hypothesis), NEUTRAL)


class FakeJudgeClient:
    def __init__(self):
        self.prompts = []

    def generate_structured(self, instructions, prompt, schema):
        self.prompts.append(prompt)
        if "market" in prompt:
            return AdditionDecision(
                reasoning="A market visit conflicts with nothing.",
                verdict=AdditionVerdict.VALID_NEW_ADDITION,
            )
        return AdditionDecision(
            reasoning="Too little context.", verdict=AdditionVerdict.INSUFFICIENT_CONTEXT
        )


def run_all():
    scorer, client, trace = ScriptedScorer(), FakeJudgeClient(), Trace()
    verifier = build_verifier(scorer, LABELS, client, trace)
    return run_benchmark(BENCHMARK, verifier, trace), scorer, client


def test_fixed_claims_are_classified_through_the_real_pipeline_after_extraction():
    records, _, _ = run_all()

    assert [r["predicted"] for r in records] == [
        "SUPPORTED",
        "CONTRADICTION",
        "VALID_NEW_ADDITION",
        "UNCERTAIN",
    ]
    assert [r["correct"] for r in records] == [True, True, True, True]


def test_claim_text_reaches_the_nli_scorer_unchanged_as_the_hypothesis():
    _, scorer, _ = run_all()

    hypotheses = {hypothesis for _, hypothesis in scorer.calls}

    assert "Ada is dead." in hypotheses
    assert hypotheses <= {c.claim for c in CLAIMS}


def test_claim_extraction_is_disabled_in_the_benchmark_verifier():
    verifier = build_verifier(ScriptedScorer(), LABELS, FakeJudgeClient(), Trace())

    with pytest.raises(RuntimeError, match="extraction"):
        verifier.extractor.extract(None)


def test_each_record_keeps_the_expected_label_the_categories_and_the_evidence():
    records, _, _ = run_all()
    first = records[1]

    assert first["claim_id"] == "W1-02"
    assert first["expected"] == "CONTRADICTION"
    assert first["expected_evidence_ids"] == ["t-001"]
    assert first["predicted_evidence_ids"] == ["t-001"]
    assert first["evidence_correct"] is True
    assert (first["category"], first["difficulty"], first["world_id"]) == ("test", "easy", "W1")


def test_relevance_nli_and_judge_details_are_recorded_per_claim():
    records, _, client = run_all()
    market = records[2]

    assert market["relevant_fact_ids"] == ["t-001", "t-002"]
    assert market["judge_consulted"] is True
    assert market["judge_verdict"] == "valid_new_addition"
    assert "conflicts with nothing" in market["judge_reasoning"]
    assert [item["premise"] for item in market["nli"]] == ["Ada status: alive", "Ada species: human"]
    assert market["nli"][0]["probabilities"] == {
        "entailment": 0.0,
        "neutral": 1.0,
        "contradiction": 0.0,
    }
    assert len(client.prompts) == 2  # only the two neutral claims reach the judge


def test_the_judge_is_not_recorded_as_consulted_for_a_supported_claim():
    records, _, _ = run_all()

    assert records[0]["judge_consulted"] is False
    assert records[0]["judge_verdict"] is None


def test_details_do_not_leak_from_one_claim_to_the_next():
    records, _, _ = run_all()

    assert records[1]["judge_verdict"] is None  # the contradiction after... never judged
    assert records[3]["judge_verdict"] == "insufficient_context"


def test_a_claim_with_no_relevant_fact_is_reported_with_no_evidence():
    stranger = make_claim("W1-05", "Lieutenant Cole commands the bay.", "UNCERTAIN")
    benchmark = Benchmark(worlds={"W1": FACTS}, claims=[stranger])
    trace = Trace()
    verifier = build_verifier(ScriptedScorer(), LABELS, FakeJudgeClient(), trace)

    (record,) = run_benchmark(benchmark, verifier, trace)

    assert record["relevant_fact_ids"] == []
    assert record["predicted"] == "UNCERTAIN"
    assert record["judge_consulted"] is False


def wrong_records():
    return [
        {
            "claim_id": "a", "world_id": "W1", "claim": "c1", "category": "x", "difficulty": "easy",
            "expected": "SUPPORTED", "predicted": "UNCERTAIN",
            "expected_evidence_ids": ["t-001"], "predicted_evidence_ids": [],
            "explanation": "no evidence", "correct": False, "evidence_correct": None,
        },
        {
            "claim_id": "b", "world_id": "W1", "claim": "c2", "category": "x", "difficulty": "easy",
            "expected": "CONTRADICTION", "predicted": "CONTRADICTION",
            "expected_evidence_ids": ["t-001"], "predicted_evidence_ids": ["t-001", "t-002"],
            "explanation": "conflict", "correct": True, "evidence_correct": False,
        },
        {
            "claim_id": "c", "world_id": "W1", "claim": "c3", "category": "x", "difficulty": "easy",
            "expected": "UNCERTAIN", "predicted": "UNCERTAIN",
            "expected_evidence_ids": [], "predicted_evidence_ids": [],
            "explanation": "ok", "correct": True, "evidence_correct": None,
        },
    ]


def test_failures_list_wrong_classes_and_wrong_evidence_with_expected_vs_predicted():
    failures = build_failures(wrong_records())

    assert [(f["claim_id"], f["failure_type"]) for f in failures] == [
        ("a", "wrong_class"),
        ("b", "wrong_evidence"),
    ]
    assert failures[0]["expected"] == "SUPPORTED"
    assert failures[0]["predicted"] == "UNCERTAIN"
    assert failures[1]["predicted_evidence_ids"] == ["t-001", "t-002"]


def test_results_are_written_as_csv_json_and_jsonl(tmp_path):
    records, _, _ = run_all()
    run_info = {"nli_model": "fake"}

    write_results(tmp_path, records, run_info)

    with (tmp_path / "predictions.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["claim_id"] for row in rows] == ["W1-01", "W1-02", "W1-03", "W1-04"]
    assert rows[1]["expected"] == "CONTRADICTION" and rows[1]["predicted"] == "CONTRADICTION"

    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["metrics"]["accuracy"] == 1.0
    assert metrics["evidence"]["evaluated"] == 2
    assert (tmp_path / "failures.jsonl").read_text(encoding="utf-8") == ""
    assert json.loads((tmp_path / "run_info.json").read_text(encoding="utf-8")) == run_info


def test_failures_file_has_one_json_object_per_failure(tmp_path):
    write_results(tmp_path, wrong_records(), {})

    lines = (tmp_path / "failures.jsonl").read_text(encoding="utf-8").splitlines()

    assert [json.loads(line)["claim_id"] for line in lines] == ["a", "b"]


# --- run information ---------------------------------------------------------------------


def test_run_info_records_the_models_thresholds_prompt_policy_and_dataset(monkeypatch):
    monkeypatch.setattr(config, "AI_API_KEY", "secret-test-key")
    verifier = build_verifier(ScriptedScorer(), LABELS, FakeJudgeClient(), Trace())
    manifest = {"claim_count": 4, "sha256": {"claims.jsonl": "abc"}}

    info = collect_run_info(manifest, verifier, nli_model="some/nli-model")

    assert info["nli_model"] == "some/nli-model"
    assert info["nli_thresholds"] == {"contradiction": 0.5, "entailment": 0.5}
    assert info["text_model"] == config.TEXT_MODEL
    assert info["ai_base_url"] == config.AI_BASE_URL
    assert info["judge_prompt_sha256"] == hashlib.sha256(ADDITION_SYSTEM_PROMPT.encode()).hexdigest()
    assert info["exclusive_predicates"] == sorted(EXCLUSIVE_PREDICATES)
    assert info["dataset"] == manifest
    assert {"git_commit", "git_dirty", "run_started_utc", "python"} <= set(info)
    assert "secret-test-key" not in json.dumps(info)


# --- orchestration -----------------------------------------------------------------------


def write_tiny_benchmark(directory):
    worlds = {"W1": {"name": "T", "facts": [f.model_dump() for f in FACTS]}}
    (directory / "worlds.json").write_text(json.dumps(worlds), encoding="utf-8")
    lines = [
        json.dumps(
            {
                "claim_id": c.claim_id, "world_id": c.world_id, "claim": c.claim,
                "expected_classification": c.expected_classification.value,
                "expected_evidence_ids": c.expected_evidence_ids,
                "category": c.category, "difficulty": c.difficulty, "rationale": c.rationale,
            }
        )
        for c in CLAIMS
    ]
    (directory / "claims.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "LABELLING_POLICY.md").write_text("policy", encoding="utf-8")


def test_an_unfrozen_dataset_is_refused_before_anything_runs(tmp_path):
    bench, out = tmp_path / "bench", tmp_path / "out"
    bench.mkdir()
    write_tiny_benchmark(bench)
    scorer = ScriptedScorer()

    with pytest.raises(DatasetNotFrozenError):
        run_evaluation(bench, out, scorer, LABELS, FakeJudgeClient(), nli_model="fake")

    assert scorer.calls == [] and not out.exists()


def test_a_dataset_edited_after_freezing_is_refused(tmp_path):
    bench, out = tmp_path / "bench", tmp_path / "out"
    bench.mkdir()
    write_tiny_benchmark(bench)
    write_manifest(bench)
    (bench / "LABELLING_POLICY.md").write_text("edited", encoding="utf-8")

    with pytest.raises(DatasetModifiedError):
        run_evaluation(bench, out, ScriptedScorer(), LABELS, FakeJudgeClient(), nli_model="fake")


def test_a_frozen_dataset_runs_and_writes_a_results_folder(tmp_path):
    bench, out = tmp_path / "bench", tmp_path / "out"
    bench.mkdir()
    write_tiny_benchmark(bench)
    write_manifest(bench)

    run_dir = run_evaluation(bench, out, ScriptedScorer(), LABELS, FakeJudgeClient(), nli_model="fake")

    assert run_dir.parent == out
    assert {p.name for p in run_dir.iterdir()} == {
        "predictions.csv",
        "metrics.json",
        "failures.jsonl",
        "run_info.json",
    }
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    assert info["dataset"]["claim_count"] == 4
