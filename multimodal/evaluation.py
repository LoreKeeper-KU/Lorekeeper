#Authored by Saif Altamimi 14/11/2026

"""Evaluate the visual module against human judgement.

Step 1 - run every scenario through the real pipeline (makes PAID API calls):
    python -m multimodal.evaluation run
    python -m multimodal.evaluation run --only S03 S05     (re-run just some)

Step 2 - open the images and fill in the human_* columns of
    multimodal/eval_results.csv   (match / mismatch / unable_to_assess)

Step 3 - print the results:
    python -m multimodal.evaluation summarize
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from multimodal.visuals import (
    build_visual_report,
    check_visual_facts,
    generate_visual,
    repair_visual,
)
from shared.ai_client import AIClient, AIClientError
from shared.schemas import CanonFact

SCENARIOS_PATH = Path("multimodal/eval_scenarios.json")
RESULTS_PATH = Path("multimodal/eval_results.csv")
STATUSES = {"match", "mismatch", "unable_to_assess"}
HUMAN_STATUS_COLUMNS = ["human_initial_status", "human_final_status"]


# ----------------------------------------------------------------------
# Step 1: run the scenarios
# ----------------------------------------------------------------------


def load_scenarios(path: Path = SCENARIOS_PATH) -> list[dict]:
    """Read the scenarios file and turn fact ids into CanonFact objects."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    facts = data["facts"]
    scenarios = []
    for scenario in data["scenarios"]:
        canon = [CanonFact(id=fact_id, **facts[fact_id]) for fact_id in scenario["canon"]]
        wrong_values = scenario.get("generate_with", {})
        # The facts used to GENERATE the image: canon, with any injected error swapped in.
        # The image is always CHECKED against the true canon.
        generate_facts = [
            fact.model_copy(update={"object": wrong_values[fact.id]})
            if fact.id in wrong_values
            else fact
            for fact in canon
        ]
        scenarios.append(
            {
                **scenario,
                "canon_facts": canon,
                "generate_facts": generate_facts,
                "injected_ids": set(wrong_values),
            }
        )
    return scenarios


def run_scenario(scenario: dict, ai) -> list[dict]:
    """Run one scenario (generate -> verify -> repair) and return one row per fact."""
    canon = scenario["canon_facts"]

    # 1. Generate the image (from the injected facts, if any)
    asset = generate_visual(scenario["scene"], scenario["generate_facts"], ai=ai)

    # 2. Verify it against the TRUE canon, keeping every per-fact verdict
    initial = check_visual_facts(asset, canon, ai=ai)
    report = build_visual_report(asset, canon, initial)

    # 3. Repair if needed, then get per-fact verdicts for the final image
    repair = repair_visual(asset, report, canon, ai=ai)
    final = check_visual_facts(repair.asset, canon, ai=ai) if repair.attempts else initial

    initial_by_id = {check.fact_id: check for check in initial.checks}
    final_by_id = {check.fact_id: check for check in final.checks}
    vision_calls = 1 + repair.attempts + (1 if repair.attempts else 0)

    rows = []
    for fact in canon:
        first = initial_by_id.get(fact.id)
        last = final_by_id.get(fact.id)
        rows.append(
            {
                "scenario_id": scenario["id"],
                "kind": scenario["kind"],
                "fact_id": fact.id,
                "injected": fact.id in scenario["injected_ids"],
                "subject": fact.subject,
                "attribute": fact.predicate,
                "expected": fact.object,
                "initial_image": asset.image_path,
                "initial_verifier": first.status if first else "unable_to_assess",
                "initial_observed": first.observed if first else "",
                "repair_attempts": repair.attempts,
                "final_image": repair.asset.image_path,
                "final_verifier": last.status if last else "unable_to_assess",
                "final_observed": last.observed if last else "",
                "final_consistent": repair.report.consistent,
                "needs_human_review": repair.needs_human_review,
                "images_generated": 1,
                "edits": repair.attempts,
                "vision_calls": vision_calls,
                "human_initial_status": "",
                "human_final_status": "",
                "human_notes": "",
            }
        )
    return rows


def has_human_judgements(df: pd.DataFrame) -> bool:
    """True if anyone has already typed a human verdict into the table."""
    return any((df[col].astype(str).str.strip() != "").any() for col in HUMAN_STATUS_COLUMNS)


def run_evaluation(
    scenarios_path: Path = SCENARIOS_PATH,
    results_path: Path = RESULTS_PATH,
    ai=None,
    only: list[str] | None = None,
    force: bool = False,
) -> pd.DataFrame:
    """Run the scenarios and save the results table (saved after EVERY scenario)."""
    ai = ai or AIClient()
    results_path = Path(results_path)
    scenarios = load_scenarios(scenarios_path)
    if only:
        scenarios = [s for s in scenarios if s["id"] in only]

    existing = pd.DataFrame()
    if results_path.exists():
        existing = pd.read_csv(results_path, keep_default_na=False)
        ids_to_replace = {s["id"] for s in scenarios}
        replaced = existing[existing["scenario_id"].isin(ids_to_replace)]
        if not force and not replaced.empty and has_human_judgements(replaced):
            raise SystemExit(
                "These scenarios already have human verdicts that would be overwritten. "
                "Use --only for other scenarios, or --force to overwrite."
            )
        existing = existing[~existing["scenario_id"].isin(ids_to_replace)]

    table = existing
    for number, scenario in enumerate(scenarios, start=1):
        print(f"[{number}/{len(scenarios)}] {scenario['id']}: {scenario['scene']}")
        try:
            rows = run_scenario(scenario, ai)
        except AIClientError as exc:
            print(f"    FAILED, skipped: {exc}")
            continue
        table = pd.concat([table, pd.DataFrame(rows)], ignore_index=True)
        table = table.sort_values(["scenario_id", "fact_id"], ignore_index=True)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(results_path, index=False)  # save now, so a crash loses nothing
        print(f"    edits: {rows[0]['edits']}, final consistent: {rows[0]['final_consistent']}")

    print(f"\nSaved {len(table)} rows to {results_path}")
    return table


# ----------------------------------------------------------------------
# Step 3: summarize (after the human columns are filled in)
# ----------------------------------------------------------------------


def as_bool(series: pd.Series) -> pd.Series:
    """CSV files store True/False as text; turn them back into real booleans."""
    return series.astype(str).str.strip().str.lower() == "true"


def percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}% ({part}/{whole})" if whole else "n/a (0 judged)"


def summarize(results_path: Path = RESULTS_PATH) -> dict:
    """Compare the verifier with the human verdicts and print the headline numbers."""
    df = pd.read_csv(results_path, keep_default_na=False)
    for col in HUMAN_STATUS_COLUMNS:
        df[col] = df[col].astype(str).str.strip().str.lower()
        bad = df[(df[col] != "") & ~df[col].isin(STATUSES)]
        if not bad.empty:
            rows = ", ".join(f"{r.scenario_id}/{r.fact_id}" for r in bad.itertuples())
            raise ValueError(f"{col} has values other than {sorted(STATUSES)} in: {rows}")

    repaired = df["repair_attempts"].astype(int) > 0

    # Every (verifier verdict, human verdict) pair the human judged.
    # Final-image pairs only count when a repair produced a NEW image.
    initial_pairs = df.loc[df["human_initial_status"] != "", ["initial_verifier", "human_initial_status"]]
    initial_pairs.columns = ["verifier", "human"]
    final_pairs = df.loc[repaired & (df["human_final_status"] != ""), ["final_verifier", "human_final_status"]]
    final_pairs.columns = ["verifier", "human"]
    pairs = pd.concat([initial_pairs, final_pairs], ignore_index=True)

    agree = int((pairs["verifier"] == pairs["human"]).sum())
    false_alarms = int(((pairs["verifier"] == "mismatch") & (pairs["human"] == "match")).sum())
    missed = int(((pairs["verifier"] == "match") & (pairs["human"] == "mismatch")).sum())

    # Attribute consistency, as judged by the human (only facts they could assess)
    def consistency(statuses: pd.Series) -> tuple[int, int]:
        assessable = statuses[statuses.isin({"match", "mismatch"})]
        return int((assessable == "match").sum()), len(assessable)

    final_human = df["human_final_status"].where(repaired, df["human_initial_status"])

    # Injected errors: did the verifier flag the fact we deliberately broke?
    injected = df[as_bool(df["injected"])]
    caught = int((injected["initial_verifier"] == "mismatch").sum())

    scenarios = df.drop_duplicates("scenario_id")
    results = {
        "scenarios": len(scenarios),
        "facts_checked": len(df),
        "verifier_judged_pairs": len(pairs),
        "verifier_agreement": (agree, len(pairs)),
        "false_alarms": false_alarms,
        "missed_mismatches": missed,
        "consistency_before_repair": consistency(df["human_initial_status"]),
        "consistency_after_repair": consistency(final_human),
        "injected_errors_caught": (caught, len(injected)),
        "scenarios_repaired": int((scenarios["repair_attempts"].astype(int) > 0).sum()),
        "repaired_now_consistent": int(
            (as_bool(scenarios["final_consistent"]) & (scenarios["repair_attempts"].astype(int) > 0)).sum()
        ),
        "needs_human_review": int(as_bool(scenarios["needs_human_review"]).sum()),
        "images_generated": int(scenarios["images_generated"].astype(int).sum()),
        "edits": int(scenarios["edits"].astype(int).sum()),
        "vision_calls": int(scenarios["vision_calls"].astype(int).sum()),
        "confusion": pd.crosstab(pairs["human"], pairs["verifier"]) if len(pairs) else None,
    }

    print("=== Visual module evaluation ===")
    print(f"Scenarios: {results['scenarios']}   Facts checked: {results['facts_checked']}")
    print("\nVerifier vs human")
    print(f"  Agreement:          {percent(*results['verifier_agreement'])}")
    print(f"  False alarms:       {false_alarms}  (verifier said mismatch, human saw a match)")
    print(f"  Missed mismatches:  {missed}  (verifier said match, human saw a mismatch)")
    if results["confusion"] is not None:
        print("  Rows = human, columns = verifier:")
        print("  " + results["confusion"].to_string().replace("\n", "\n  "))
    print("\nAttribute consistency (human-judged, assessable facts only)")
    print(f"  Before repair:      {percent(*results['consistency_before_repair'])}")
    print(f"  After repair:       {percent(*results['consistency_after_repair'])}")
    print(f"  Injected errors caught by verifier: {percent(*results['injected_errors_caught'])}")
    print("\nRepair")
    print(f"  Scenarios repaired: {results['scenarios_repaired']}"
          f"   now consistent: {results['repaired_now_consistent']}"
          f"   flagged for human review: {results['needs_human_review']}")
    print("\nCost (API calls)")
    print(f"  Images generated: {results['images_generated']}   Edits: {results['edits']}"
          f"   Vision checks: {results['vision_calls']}")
    print("  Check the OpenAI usage page for the exact spend of the run.")
    return results


# ----------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the LoreKeeper visual module.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run scenarios through the real pipeline (paid)")
    run.add_argument("--only", nargs="+", help="scenario ids to run, e.g. S03 S05")
    run.add_argument("--force", action="store_true", help="overwrite human verdicts")
    sub.add_parser("summarize", help="compare verifier with human verdicts")
    args = parser.parse_args()

    if args.command == "run":
        run_evaluation(only=args.only, force=args.force)
    else:
        summarize()


if __name__ == "__main__":
    main()
