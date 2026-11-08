"""The development set: its shape, its labels, its separation from the frozen benchmark."""

import json
import re
from collections import Counter

import pytest

from evaluation.dataset import (
    BENCHMARK_DIR,
    DEVSET_DIR,
    load_benchmark,
    verify_manifest,
)
from evaluation.runner import RESULTS_DEV_DIR, RESULTS_DIR, resolve_set

EXPECTED_BY_CLASS = {"SUPPORTED": 5, "CONTRADICTION": 11, "VALID_NEW_ADDITION": 7, "UNCERTAIN": 7}

EXPECTED_BY_FOCUS = {
    "paraphrase": 2,
    "father_mother": 2,
    "house_allegiance": 2,
    "implicit_status": 3,
    "non_exclusive_unnamed": 2,
    "same_entity_event": 4,
    "thin_context": 2,
    "relation_unnamed": 4,
    "non_exclusive": 1,
    "distractor": 1,
    "core_unsettled": 2,
    "same_entity_prop": 1,
    "exact": 1,
    "partial": 1,
    "negation": 1,
    "entity_absent": 1,
}


@pytest.fixture(scope="module")
def dev():
    return load_benchmark(DEVSET_DIR)


@pytest.fixture(scope="module")
def frozen():
    return load_benchmark(BENCHMARK_DIR)


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


# --- shape and labels ---------------------------------------------------------------------


def test_devset_has_30_claims_with_the_approved_class_distribution(dev):
    assert len(dev.claims) == 30
    counts = Counter(c.expected_classification.value for c in dev.claims)
    assert dict(counts) == EXPECTED_BY_CLASS


def test_devset_has_the_approved_focus_breakdown(dev):
    assert dict(Counter(c.category for c in dev.claims)) == EXPECTED_BY_FOCUS


def test_devset_uses_four_worlds_named_d1_to_d4(dev):
    assert sorted(dev.worlds) == ["D1", "D2", "D3", "D4"]


def test_the_approved_wording_change_to_d2_01_is_in_place_with_its_labels_kept(dev):
    claim = next(c for c in dev.claims if c.claim_id == "D2-01")

    assert claim.claim == "Emeka Balogun is Anaya Okoro’s paternal parent."
    assert claim.expected_classification.value == "CONTRADICTION"
    assert claim.expected_evidence_ids == ["kd-001"]
    assert claim.category == "relation_unnamed"
    assert claim.difficulty == "hard"


def test_claims_that_do_not_name_the_relation_really_do_not_use_the_relation_word(dev):
    relation_words = {"father", "mother", "house", "allegiance"}
    for claim in dev.claims:
        if claim.category == "relation_unnamed":
            assert not words(claim.claim) & relation_words, claim.claim


def test_the_entity_absent_claim_shares_no_word_with_its_world(dev):
    stop = {"the", "a", "an", "of", "in", "on", "at", "under", "is", "was"}
    for claim in dev.claims:
        if claim.category == "entity_absent":
            world_words = set()
            for fact in dev.worlds[claim.world_id]:
                world_words |= words(f"{fact.subject} {fact.predicate} {fact.object}")
            assert not (words(claim.claim) - stop) & world_words


# --- separation from the frozen benchmark ---------------------------------------------------


def test_no_dev_claim_reuses_a_frozen_claim(dev, frozen):
    frozen_texts = {c.claim.lower() for c in frozen.claims}
    assert not [c.claim_id for c in dev.claims if c.claim.lower() in frozen_texts]


def test_dev_and_frozen_worlds_share_no_ids(dev, frozen):
    assert not set(dev.worlds) & set(frozen.worlds)
    dev_ids = {f.id for facts in dev.worlds.values() for f in facts}
    frozen_ids = {f.id for facts in frozen.worlds.values() for f in facts}
    assert not dev_ids & frozen_ids
    assert not {c.claim_id for c in dev.claims} & {c.claim_id for c in frozen.claims}


def test_dev_and_frozen_worlds_share_no_character_or_place_names(dev, frozen):
    dev_names = set().union(*(words(f.subject) for fs in dev.worlds.values() for f in fs))
    frozen_names = set().union(*(words(f.subject) for fs in frozen.worlds.values() for f in fs))
    assert not (dev_names & frozen_names) - {"the"}  # an article is not a name


def test_no_dev_fact_repeats_a_frozen_fact(dev, frozen):
    dev_facts = {(f.subject, f.predicate, f.object) for fs in dev.worlds.values() for f in fs}
    frozen_facts = {(f.subject, f.predicate, f.object) for fs in frozen.worlds.values() for f in fs}
    assert not dev_facts & frozen_facts


# --- manifests and the policy pointer ---------------------------------------------------------


def test_the_devset_has_its_own_manifest_and_it_verifies():
    manifest = verify_manifest(DEVSET_DIR)

    assert manifest["claim_count"] == 30


def test_the_frozen_benchmark_still_verifies_against_its_own_manifest():
    manifest = verify_manifest(BENCHMARK_DIR)

    assert manifest["claim_count"] == 52


def test_the_dev_manifest_is_separate_from_the_benchmark_manifest():
    dev = json.loads((DEVSET_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    frozen = json.loads((BENCHMARK_DIR / "MANIFEST.json").read_text(encoding="utf-8"))

    assert dev["sha256"]["claims.jsonl"] != frozen["sha256"]["claims.jsonl"]
    assert dev["sha256"]["worlds.json"] != frozen["sha256"]["worlds.json"]


def test_the_devset_policy_file_points_at_the_frozen_policy_by_hash():
    frozen = json.loads((BENCHMARK_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    pointer = (DEVSET_DIR / "LABELLING_POLICY.md").read_text(encoding="utf-8")

    assert "benchmark/LABELLING_POLICY.md" in pointer
    assert frozen["sha256"]["LABELLING_POLICY.md"] in pointer


# --- results stay apart -----------------------------------------------------------------------


def test_dev_results_go_to_their_own_folder_outside_the_benchmark_results():
    assert RESULTS_DEV_DIR.name == "results_dev"
    assert RESULTS_DEV_DIR != RESULTS_DIR
    assert RESULTS_DIR not in RESULTS_DEV_DIR.parents
    assert RESULTS_DEV_DIR not in RESULTS_DIR.parents


def test_choosing_the_dev_set_selects_dev_data_and_dev_results_together():
    assert resolve_set("dev") == (DEVSET_DIR, RESULTS_DEV_DIR)


def test_choosing_the_benchmark_keeps_the_original_locations():
    assert resolve_set("benchmark") == (BENCHMARK_DIR, RESULTS_DIR)


def test_an_unknown_set_name_is_rejected():
    with pytest.raises(ValueError, match="unknown"):
        resolve_set("test")
