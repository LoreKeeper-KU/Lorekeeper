"""Load, validate and freeze the continuity-verification benchmark.

The benchmark is data only: fictional worlds (lists of the team's CanonFact) and manually
labelled atomic claims. Nothing here imports the verifier, so the labels cannot depend on it.
"""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.schemas import CanonFact, ClaimClassification

BENCHMARK_DIR = Path(__file__).parent / "benchmark"
DEVSET_DIR = Path(__file__).parent / "devset"
HELDOUT_DIR = Path(__file__).parent / "heldout"
MANIFEST_NAME = "MANIFEST.json"
FROZEN_FILES = ("worlds.json", "claims.jsonl", "LABELLING_POLICY.md")


class BenchmarkError(ValueError):
    """The benchmark files are inconsistent."""


class DatasetNotFrozenError(RuntimeError):
    """No MANIFEST.json: the dataset has not been frozen yet."""


class DatasetModifiedError(RuntimeError):
    """A frozen file no longer matches the hash recorded when it was frozen."""


class BenchmarkClaim(BaseModel):
    """One manually defined atomic claim and its expected classification."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1)
    world_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    expected_classification: ClaimClassification
    expected_evidence_ids: list[str] = Field(default_factory=list)
    category: str = Field(min_length=1)
    difficulty: Literal["easy", "hard"]
    rationale: str = Field(min_length=1)


class Benchmark(BaseModel):
    worlds: dict[str, list[CanonFact]]
    claims: list[BenchmarkClaim]


_NEEDS_EVIDENCE = {ClaimClassification.SUPPORTED, ClaimClassification.CONTRADICTION}


def load_benchmark(directory: Path = BENCHMARK_DIR) -> Benchmark:
    directory = Path(directory)
    raw_worlds = json.loads((directory / "worlds.json").read_text(encoding="utf-8"))
    worlds = {
        world_id: [CanonFact(**fact) for fact in world["facts"]]
        for world_id, world in raw_worlds.items()
    }
    lines = (directory / "claims.jsonl").read_text(encoding="utf-8").splitlines()
    claims = [BenchmarkClaim(**json.loads(line)) for line in lines if line.strip()]

    _validate(worlds, claims)
    return Benchmark(worlds=worlds, claims=claims)


def _validate(worlds: dict[str, list[CanonFact]], claims: list[BenchmarkClaim]) -> None:
    fact_ids = [fact.id for facts in worlds.values() for fact in facts]
    if len(fact_ids) != len(set(fact_ids)):
        raise BenchmarkError("duplicate fact ids across worlds")

    claim_ids = [claim.claim_id for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise BenchmarkError("duplicate claim ids")

    for claim in claims:
        if claim.world_id not in worlds:
            raise BenchmarkError(f"{claim.claim_id}: unknown world {claim.world_id}")
        world_fact_ids = {fact.id for fact in worlds[claim.world_id]}
        for evidence_id in claim.expected_evidence_ids:
            if evidence_id not in world_fact_ids:
                raise BenchmarkError(
                    f"{claim.claim_id}: evidence {evidence_id} is not in world {claim.world_id}"
                )
        needs = claim.expected_classification in _NEEDS_EVIDENCE
        if needs and not claim.expected_evidence_ids:
            raise BenchmarkError(f"{claim.claim_id}: expected evidence ids are required")
        if not needs and claim.expected_evidence_ids:
            raise BenchmarkError(
                f"{claim.claim_id}: {claim.expected_classification.value} claims must not "
                "list expected evidence ids"
            )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_hashes(directory: Path = BENCHMARK_DIR) -> dict[str, str]:
    directory = Path(directory)
    return {name: _sha256(directory / name) for name in FROZEN_FILES}


def write_manifest(directory: Path = BENCHMARK_DIR) -> dict:
    """Freeze the dataset: record each file's hash and the claim count."""
    directory = Path(directory)
    manifest = {
        "claim_count": len(load_benchmark(directory).claims),
        "sha256": dataset_hashes(directory),
    }
    (directory / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def freeze() -> None:
    """Command line: python -m evaluation.dataset  (freeze the dataset after label review)."""
    manifest = write_manifest()
    print(f"frozen {manifest['claim_count']} claims")
    for name, digest in manifest["sha256"].items():
        print(f"  {name}: {digest}")


def verify_manifest(directory: Path = BENCHMARK_DIR) -> dict:
    """Raise unless the dataset on disk is exactly what was frozen."""
    directory = Path(directory)
    path = directory / MANIFEST_NAME
    if not path.exists():
        raise DatasetNotFrozenError(f"{path} not found: freeze the dataset before running")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for name, recorded in manifest["sha256"].items():
        if _sha256(directory / name) != recorded:
            raise DatasetModifiedError(f"{name} changed after the dataset was frozen")
    return manifest


if __name__ == "__main__":
    freeze()
