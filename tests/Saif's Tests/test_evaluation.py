#Authored By Saif Altamimi 14/11/2026

"""Tests for multimodal/evaluation.py. No API calls: a fake AI client is used."""
import pandas as pd
import pytest

from multimodal.evaluation import load_scenarios, run_evaluation, run_scenario, summarize
from multimodal.model import FactCheck, VisionCheckResult


class FakeAIClient:
    """Answers every vision check with the statuses we give it, per fact id."""

    def __init__(self, first: dict, after_edit: dict | None = None):
        self.first = first  # verdicts for the first check
        self.after_edit = after_edit or first  # verdicts once an image was edited
        self.edits = 0

    def generate_image(self, prompt):
        return "outputs/fake.png"

    def edit_image(self, image_path, prompt):
        self.edits += 1
        return f"outputs/fake_edit_{self.edits}.png"

    def analyze_image(self, image_path, prompt, schema=None):
        verdicts = self.after_edit if "fake_edit" in image_path else self.first
        return VisionCheckResult(
            checks=[
                FactCheck(fact_id=fid, status=status, observed="x", explanation="test")
                for fid, status in verdicts.items()
            ]
        )


def scenario(scenario_id):
    return next(s for s in load_scenarios() if s["id"] == scenario_id)


# --- loading -------------------------------------------------------------------

def test_load_scenarios_has_ten_with_injected_errors():
    scenarios = load_scenarios()
    assert len(scenarios) == 10
    assert sum(s["kind"] == "injected" for s in scenarios) == 4


def test_injected_error_changes_generation_but_not_canon():
    s03 = scenario("S03")
    canon_armor = next(f for f in s03["canon_facts"] if f.id == "F004")
    generated_armor = next(f for f in s03["generate_facts"] if f.id == "F004")
    assert canon_armor.object == "silver"  # checked against the truth
    assert generated_armor.object == "gold"  # generated with the mistake


# --- running ---------------------------------------------------------------------

def test_run_scenario_records_repair_and_one_row_per_fact():
    fake = FakeAIClient(
        first={"F001": "match", "F004": "mismatch"},
        after_edit={"F001": "match", "F004": "match"},
    )
    rows = run_scenario(scenario("S03"), fake)

    assert [r["fact_id"] for r in rows] == ["F001", "F004"]
    armor = rows[1]
    assert armor["injected"] is True
    assert armor["initial_verifier"] == "mismatch"
    assert armor["final_verifier"] == "match"
    assert armor["repair_attempts"] == 1
    assert armor["vision_calls"] == 3  # first check + check inside repair + final check


def test_run_refuses_to_overwrite_human_verdicts(tmp_path):
    results = tmp_path / "results.csv"
    pd.DataFrame(
        [{"scenario_id": "S01", "fact_id": "F001", "human_initial_status": "match",
          "human_final_status": ""}]
    ).to_csv(results, index=False)
    fake = FakeAIClient(first={"F001": "match", "F004": "match", "F005": "match"})

    with pytest.raises(SystemExit):
        run_evaluation(results_path=results, ai=fake, only=["S01"])


# --- summarizing -------------------------------------------------------------------

def test_summarize_counts_agreement_and_errors(tmp_path):
    fake = FakeAIClient(
        first={"F001": "match", "F004": "mismatch"},
        after_edit={"F001": "match", "F004": "match"},
    )
    results = tmp_path / "results.csv"
    table = run_evaluation(results_path=results, ai=fake, only=["S03"])

    # The human agrees about the hair, and agrees the armor was fixed,
    # but says the first image's armor was actually fine (a false alarm).
    table["human_initial_status"] = ["match", "match"]
    table["human_final_status"] = ["match", "match"]
    table.to_csv(results, index=False)

    summary = summarize(results)
    assert summary["facts_checked"] == 2
    assert summary["verifier_agreement"] == (3, 4)  # 2 initial + 2 final pairs (image was repaired)
    assert summary["false_alarms"] == 1
    assert summary["missed_mismatches"] == 0
    assert summary["injected_errors_appeared"] == (0, 1)  # human says the gold never appeared
    assert summary["injected_errors_caught"] == (0, 0)  # so there was nothing to catch
    assert summary["scenarios_repaired"] == 1


def test_summarize_rejects_typos_in_human_columns(tmp_path):
    fake = FakeAIClient(first={"F001": "match", "F004": "match", "F005": "match"})
    results = tmp_path / "results.csv"
    table = run_evaluation(results_path=results, ai=fake, only=["S01"])
    table.loc[0, "human_initial_status"] = "matchh"
    table.to_csv(results, index=False)

    with pytest.raises(ValueError, match="matchh|S01/F001"):
        summarize(results)


def test_summarize_reads_csv_saved_by_excel_on_windows(tmp_path):
    # Excel on Windows saves CSVs in "cp1252", where an en dash is byte 0x96
    fake = FakeAIClient(first={"F001": "match", "F004": "match", "F005": "match"})
    results = tmp_path / "results.csv"
    table = run_evaluation(results_path=results, ai=fake, only=["S01"])
    table["human_initial_status"] = "match"
    table.loc[0, "human_notes"] = "hair clearly black \u2013 easy to see"
    table.to_csv(results, index=False, encoding="cp1252")

    summary = summarize(results)
    assert summary["verifier_agreement"] == (3, 3)
