# Authored by Faris
"""The held-out set: its shape, its labels, and its separation from the benchmark and dev set."""

import difflib
import json
import re
from collections import Counter

import pytest

from evaluation.dataset import (
    BENCHMARK_DIR,
    DEVSET_DIR,
    HELDOUT_DIR,
    load_benchmark,
    verify_manifest,
)
from evaluation.runner import (
    RESULTS_DEV_DIR,
    RESULTS_DIR,
    RESULTS_HELDOUT_DIR,
    SET_NAMES,
    resolve_set,
)

EXPECTED_BY_CLASS = {"SUPPORTED": 8, "CONTRADICTION": 8, "VALID_NEW_ADDITION": 8, "UNCERTAIN": 8}

EXPECTED_BY_FOCUS = {
    "exact": 1,
    "paraphrase": 4,
    "negation": 1,
    "distractor": 2,
    "father_mother": 1,
    "house_allegiance": 1,
    "relation_unnamed": 3,
    "implicit_status": 2,
    "ability": 1,
    "same_entity_event": 3,
    "thin_context": 3,
    "interaction": 2,
    "non_exclusive": 1,
    "non_exclusive_unnamed": 1,
    "core_unsettled": 2,
    "partial": 2,
    "entity_absent": 2,
}


@pytest.fixture(scope="module")
def heldout():
    return load_benchmark(HELDOUT_DIR)


@pytest.fixture(scope="module")
def prior():
    """The two earlier sets, which the held-out set must not overlap."""
    return [load_benchmark(BENCHMARK_DIR), load_benchmark(DEVSET_DIR)]


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


# --- shape and labels ---------------------------------------------------------------------


def test_heldout_has_32_claims_with_eight_in_each_class(heldout):
    assert len(heldout.claims) == 32
    counts = Counter(c.expected_classification.value for c in heldout.claims)
    assert dict(counts) == EXPECTED_BY_CLASS


def test_heldout_has_four_worlds_with_two_claims_of_each_class_in_each(heldout):
    assert sorted(heldout.worlds) == ["H1", "H2", "H3", "H4"]
    per_world = Counter((c.world_id, c.expected_classification.value) for c in heldout.claims)
    for world_id in heldout.worlds:
        for label in EXPECTED_BY_CLASS:
            assert per_world[(world_id, label)] == 2, (world_id, label)


def test_heldout_has_the_approved_focus_breakdown(heldout):
    assert dict(Counter(c.category for c in heldout.claims)) == EXPECTED_BY_FOCUS


def test_heldout_mixes_easy_and_hard_claims(heldout):
    hard = sum(1 for c in heldout.claims if c.difficulty == "hard")
    assert hard == 12
    assert len(heldout.claims) - hard == 20


@pytest.mark.parametrize(
    "claim_id, text, rationale_word",
    [
        ("H2-07", "Prince Tavian Orsolo has a younger brother named Lucan.", "siblings"),
        ("H4-07", "Aurelio Bastien has a daughter named Mireya.", "children"),
    ],
)
def test_the_two_approved_wording_changes_are_in_place_with_their_labels_kept(
    heldout, claim_id, text, rationale_word
):
    claim = next(c for c in heldout.claims if c.claim_id == claim_id)

    assert claim.claim == text
    assert claim.expected_classification.value == "UNCERTAIN"
    assert claim.expected_evidence_ids == []
    assert claim.category == "core_unsettled"
    assert claim.difficulty == "hard"
    assert rationale_word in claim.rationale


def test_claims_that_do_not_name_the_relation_do_not_use_the_relation_words(heldout):
    relation_words = {"father", "mother", "house", "allegiance", "birthplace"}
    for claim in heldout.claims:
        if claim.category == "relation_unnamed":
            assert not words(claim.claim) & relation_words, claim.claim


def test_the_entity_absent_claims_share_no_word_with_their_world(heldout):
    stop = {"the", "a", "an", "of", "in", "on", "at", "under", "is", "was", "s"}
    for claim in heldout.claims:
        if claim.category == "entity_absent":
            world_words = set()
            for fact in heldout.worlds[claim.world_id]:
                world_words |= words(f"{fact.subject} {fact.predicate} {fact.object}")
            assert not (words(claim.claim) - stop) & world_words, claim.claim


# --- separation from the benchmark and the dev set -------------------------------------------


def test_no_heldout_claim_reuses_a_claim_from_the_other_sets(heldout, prior):
    old = {c.claim.lower() for ds in prior for c in ds.claims}
    assert not [c.claim_id for c in heldout.claims if c.claim.lower() in old]


def test_no_heldout_claim_is_a_near_copy_of_an_earlier_claim(heldout, prior):
    # Two claims were deliberately given the same sentence pattern as W1-08 and W4-07; every
    # claim must still stay clearly below a near-duplicate.
    old = [c.claim.lower() for ds in prior for c in ds.claims]
    for claim in heldout.claims:
        best = max(difflib.SequenceMatcher(None, claim.claim.lower(), o).ratio() for o in old)
        assert best < 0.8, (claim.claim_id, best)


def test_heldout_shares_no_ids_with_the_other_sets(heldout, prior):
    for ds in prior:
        assert not set(heldout.worlds) & set(ds.worlds)
        assert not {c.claim_id for c in heldout.claims} & {c.claim_id for c in ds.claims}
        held_ids = {f.id for fs in heldout.worlds.values() for f in fs}
        assert not held_ids & {f.id for fs in ds.worlds.values() for f in fs}


def test_no_heldout_fact_repeats_a_fact_from_the_other_sets(heldout, prior):
    held = {(f.subject, f.predicate, f.object) for fs in heldout.worlds.values() for f in fs}
    for ds in prior:
        old = {(f.subject, f.predicate, f.object) for fs in ds.worlds.values() for f in fs}
        assert not held & old


def test_heldout_characters_and_places_share_no_name_with_the_other_sets(heldout, prior):
    held_names = set().union(*(words(f.subject) for fs in heldout.worlds.values() for f in fs))
    for ds in prior:
        old = set()
        for fs in ds.worlds.values():
            for f in fs:
                old |= words(f.subject) | words(f.object)
        assert not (held_names & old) - {"the"}  # an article is not a name


# --- manifests and the policy pointer ---------------------------------------------------------


def test_the_heldout_set_has_its_own_manifest_and_it_verifies():
    assert verify_manifest(HELDOUT_DIR)["claim_count"] == 32


def test_the_earlier_sets_still_verify_against_their_own_manifests():
    assert verify_manifest(BENCHMARK_DIR)["claim_count"] == 52
    assert verify_manifest(DEVSET_DIR)["claim_count"] == 30


def test_the_three_manifests_are_different():
    hashes = []
    for directory in (BENCHMARK_DIR, DEVSET_DIR, HELDOUT_DIR):
        manifest = json.loads((directory / "MANIFEST.json").read_text(encoding="utf-8"))
        hashes.append(manifest["sha256"]["claims.jsonl"])
    assert len(set(hashes)) == 3


def test_the_heldout_policy_file_points_at_the_frozen_policy_by_hash():
    frozen = json.loads((BENCHMARK_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    pointer = (HELDOUT_DIR / "LABELLING_POLICY.md").read_text(encoding="utf-8")

    assert "benchmark/LABELLING_POLICY.md" in pointer
    assert frozen["sha256"]["LABELLING_POLICY.md"] in pointer


# --- the run option and separate results ------------------------------------------------------


def test_the_runner_offers_all_three_sets():
    assert SET_NAMES == ("benchmark", "dev", "heldout")


def test_choosing_the_heldout_set_selects_its_data_and_its_own_results_folder():
    assert resolve_set("heldout") == (HELDOUT_DIR, RESULTS_HELDOUT_DIR)


def test_the_other_sets_keep_their_locations():
    assert resolve_set("benchmark")[1] == RESULTS_DIR
    assert resolve_set("dev")[1] == RESULTS_DEV_DIR


def test_the_three_results_folders_are_separate_and_not_nested():
    folders = [RESULTS_DIR, RESULTS_DEV_DIR, RESULTS_HELDOUT_DIR]
    assert RESULTS_HELDOUT_DIR.name == "results_heldout"
    assert len(set(folders)) == 3
    for a in folders:
        for b in folders:
            if a != b:
                assert a not in b.parents
