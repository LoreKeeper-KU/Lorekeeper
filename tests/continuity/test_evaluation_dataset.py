# Authored by Faris
"""The benchmark loader, its validation, the freeze manifest, and the real dataset's shape."""

import json
from collections import Counter

import pytest

from evaluation.dataset import (
    BENCHMARK_DIR,
    BenchmarkError,
    DatasetModifiedError,
    DatasetNotFrozenError,
    load_benchmark,
    verify_manifest,
    write_manifest,
)

WORLD = {
    "W1": {
        "name": "Test World",
        "facts": [
            {"id": "t-001", "subject": "Ada", "predicate": "status", "object": "alive"},
            {"id": "t-002", "subject": "Ada", "predicate": "species", "object": "human"},
        ],
    }
}


def claim_line(**overrides):
    record = {
        "claim_id": "W1-01",
        "world_id": "W1",
        "claim": "Ada is alive.",
        "expected_classification": "SUPPORTED",
        "expected_evidence_ids": ["t-001"],
        "category": "exact",
        "difficulty": "easy",
        "rationale": "Restates the status fact.",
    }
    record.update(overrides)
    return json.dumps(record)


def write_benchmark(directory, claim_lines, worlds=WORLD):
    (directory / "worlds.json").write_text(json.dumps(worlds), encoding="utf-8")
    (directory / "claims.jsonl").write_text("\n".join(claim_lines) + "\n", encoding="utf-8")
    (directory / "LABELLING_POLICY.md").write_text("policy", encoding="utf-8")


# --- loader ------------------------------------------------------------------------------


def test_loader_returns_worlds_as_team_canon_facts_and_typed_claims(tmp_path):
    write_benchmark(tmp_path, [claim_line()])

    benchmark = load_benchmark(tmp_path)

    assert [f.id for f in benchmark.worlds["W1"]] == ["t-001", "t-002"]
    (claim,) = benchmark.claims
    assert claim.claim == "Ada is alive."
    assert claim.expected_classification.value == "SUPPORTED"
    assert claim.expected_evidence_ids == ["t-001"]


def test_loader_rejects_evidence_that_is_not_in_the_claims_world(tmp_path):
    write_benchmark(tmp_path, [claim_line(expected_evidence_ids=["t-999"])])

    with pytest.raises(BenchmarkError, match="t-999"):
        load_benchmark(tmp_path)


def test_loader_rejects_a_claim_for_an_unknown_world(tmp_path):
    write_benchmark(tmp_path, [claim_line(world_id="W9")])

    with pytest.raises(BenchmarkError, match="W9"):
        load_benchmark(tmp_path)


def test_loader_rejects_duplicate_claim_ids(tmp_path):
    write_benchmark(tmp_path, [claim_line(), claim_line()])

    with pytest.raises(BenchmarkError, match="duplicate"):
        load_benchmark(tmp_path)


def test_loader_rejects_unknown_classification(tmp_path):
    write_benchmark(tmp_path, [claim_line(expected_classification="MAYBE")])

    with pytest.raises(Exception, match="expected_classification"):
        load_benchmark(tmp_path)


def test_supported_and_contradiction_claims_must_name_their_evidence(tmp_path):
    write_benchmark(tmp_path, [claim_line(expected_evidence_ids=[])])

    with pytest.raises(BenchmarkError, match="evidence"):
        load_benchmark(tmp_path)


def test_other_classes_must_not_name_evidence(tmp_path):
    write_benchmark(
        tmp_path,
        [claim_line(expected_classification="UNCERTAIN", expected_evidence_ids=["t-001"])],
    )

    with pytest.raises(BenchmarkError, match="evidence"):
        load_benchmark(tmp_path)


# --- freezing ----------------------------------------------------------------------------


def test_an_unfrozen_dataset_is_refused(tmp_path):
    write_benchmark(tmp_path, [claim_line()])

    with pytest.raises(DatasetNotFrozenError):
        verify_manifest(tmp_path)


def test_a_frozen_dataset_verifies(tmp_path):
    write_benchmark(tmp_path, [claim_line()])
    write_manifest(tmp_path)

    verify_manifest(tmp_path)


def test_editing_a_label_after_freezing_is_detected(tmp_path):
    write_benchmark(tmp_path, [claim_line()])
    write_manifest(tmp_path)

    write_benchmark(tmp_path, [claim_line(expected_classification="UNCERTAIN", expected_evidence_ids=[])])

    with pytest.raises(DatasetModifiedError, match="claims.jsonl"):
        verify_manifest(tmp_path)


def test_editing_the_facts_after_freezing_is_detected(tmp_path):
    write_benchmark(tmp_path, [claim_line()])
    write_manifest(tmp_path)

    changed = json.loads(json.dumps(WORLD))
    changed["W1"]["facts"][0]["object"] = "dead"
    write_benchmark(tmp_path, [claim_line()], worlds=changed)

    with pytest.raises(DatasetModifiedError, match="worlds.json"):
        verify_manifest(tmp_path)


def test_manifest_records_the_claim_count_and_file_hashes(tmp_path):
    write_benchmark(tmp_path, [claim_line()])
    write_manifest(tmp_path)

    manifest = json.loads((tmp_path / "MANIFEST.json").read_text(encoding="utf-8"))

    assert manifest["claim_count"] == 1
    assert set(manifest["sha256"]) == {"worlds.json", "claims.jsonl", "LABELLING_POLICY.md"}


# --- the real benchmark's shape ------------------------------------------------------------

EXPECTED_BY_CLASS = {"SUPPORTED": 12, "CONTRADICTION": 14, "VALID_NEW_ADDITION": 12, "UNCERTAIN": 14}

EXPECTED_BY_CATEGORY = {
    "SUPPORTED": {"exact": 3, "paraphrase": 4, "negation": 2, "distractor": 3},
    "CONTRADICTION": {
        "status": 3,
        "species": 2,
        "appearance_birthplace": 2,
        "ability": 2,
        "family": 3,
        "allegiance": 2,
    },
    "VALID_NEW_ADDITION": {"event": 5, "interaction": 3, "background": 4},
    "UNCERTAIN": {"non_exclusive": 4, "core_unsettled": 4, "entity_absent": 3, "partial": 3},
}


@pytest.fixture(scope="module")
def real():
    return load_benchmark(BENCHMARK_DIR)


def test_benchmark_has_52_claims_with_the_approved_class_distribution(real):
    assert len(real.claims) == 52
    counts = Counter(c.expected_classification.value for c in real.claims)
    assert dict(counts) == EXPECTED_BY_CLASS


def test_benchmark_has_the_approved_category_breakdown_inside_each_class(real):
    counts = Counter((c.expected_classification.value, c.category) for c in real.claims)
    expected = {
        (label, category): n
        for label, categories in EXPECTED_BY_CATEGORY.items()
        for category, n in categories.items()
    }
    assert dict(counts) == expected


def test_benchmark_uses_five_worlds_with_every_class_at_least_twice_in_each(real):
    assert len(real.worlds) == 5
    per_world = Counter((c.world_id, c.expected_classification.value) for c in real.claims)
    for world_id in real.worlds:
        for label in EXPECTED_BY_CLASS:
            assert per_world[(world_id, label)] >= 2, (world_id, label)


def test_benchmark_mixes_easy_and_hard_claims(real):
    hard = sum(1 for c in real.claims if c.difficulty == "hard")
    assert 0.3 <= hard / len(real.claims) <= 0.5


def test_benchmark_does_not_reuse_the_arin_or_amina_examples(real):
    text = json.dumps([c.claim for c in real.claims]) + json.dumps(
        [f.model_dump() for facts in real.worlds.values() for f in facts]
    )
    assert "Arin" not in text and "Amina" not in text


def test_benchmark_claim_texts_are_unique(real):
    texts = [c.claim for c in real.claims]
    assert len(texts) == len(set(texts))


def test_benchmark_fact_ids_are_unique_across_worlds(real):
    ids = [f.id for facts in real.worlds.values() for f in facts]
    assert len(ids) == len(set(ids))
