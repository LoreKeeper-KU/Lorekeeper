# Authored by Abdullah on 19/11/2026
# Offline integration checks. No API key or model download is needed.

import json
import unittest

from types import SimpleNamespace
from unittest.mock import Mock

from generation_engine.ai_story_generator import AIStoryGenerator
from generation_engine.models import DemoRequest
from generation_engine.team_pipeline import (
    TeamServices,
    run_team_pipeline,
)

from shared.schemas import (
    CanonFact,
    ClaimAssessment,
    ClaimClassification,
    VerificationReport,
    VisualAsset,
    VisualReport,
)


def report(category):
    """Build a small shared report for a test."""

    return VerificationReport(
        claims=[
            ClaimAssessment(
                claim="Amina acts.",
                classification=category,
                reason="Test evidence.",
                evidence_fact_ids=["F1"],
            )
        ]
    )


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.facts = [
            CanonFact(
                id="F1",
                subject="char_amina",
                predicate="magic_ability",
                object="none",
            )
        ]

        self.request = DemoRequest(
            prompt="Amina",
            mode="verified",
            max_repair_attempts=3,
        )

        self.services = TeamServices(
            retrieve=Mock(return_value=self.facts),
            generate=Mock(return_value="initial scene"),
            verify=Mock(
                return_value=report(
                    ClaimClassification.SUPPORTED
                )
            ),
            repair=Mock(return_value="repaired scene"),
            generate_visual=Mock(
                return_value=VisualAsset(
                    image_path="test.png",
                    prompt="test",
                )
            ),
            check_visual=Mock(
                return_value=self.checks("match")
            ),
            build_visual_report=self.build_report,
            repair_visual=Mock(),
        )

    @staticmethod
    def checks(status):
        return SimpleNamespace(
            checks=[
                SimpleNamespace(
                    fact_id="F1",
                    status=status,
                    explanation="Test observation.",
                )
            ]
        )

    @staticmethod
    def build_report(asset, facts, checks):
        mismatches = [
            check
            for check in checks.checks
            if check.status == "mismatch"
        ]

        return VisualReport(
            image_path=asset.image_path,
            consistent=not mismatches,
            issues=["Test mismatch"] if mismatches else [],
            evidence_fact_ids=[
                check.fact_id for check in mismatches
            ],
        )

    def test_same_retrieved_snapshot_is_used_for_text_and_visuals(self):
        result = run_team_pipeline(
            self.request,
            self.services,
            include_visuals=True,
        )

        self.assertEqual(
            result.visual_status,
            "no_mismatches_detected",
        )

        self.services.retrieve.assert_called_once_with(
            "Amina"
        )

        for callback in (
            self.services.generate,
            self.services.verify,
            self.services.generate_visual,
            self.services.check_visual,
        ):
            self.assertIs(
                callback.call_args.args[1],
                self.facts,
            )

    def test_missing_canon_stops_before_generation(self):
        self.services.retrieve.return_value = []

        with self.assertRaisesRegex(
            ValueError,
            "No approved canon",
        ):
            run_team_pipeline(
                self.request,
                self.services,
            )

        self.services.generate.assert_not_called()

    def test_contradiction_is_repaired_despite_an_uncertain_claim(self):
        initial = report(
            ClaimClassification.CONTRADICTION
        )

        initial.claims += report(
            ClaimClassification.UNCERTAIN
        ).claims

        self.services.verify.side_effect = [
            initial,
            report(ClaimClassification.SUPPORTED),
        ]

        result = run_team_pipeline(
            self.request,
            self.services,
        )

        self.assertEqual(result.text.status, "verified")
        self.assertEqual(result.text.final_scene.revision, 1)
        self.assertEqual(result.text.repair_attempts, 1)
        self.assertEqual(len(result.text.reports), 2)

        self.assertIs(
            self.services.repair.call_args.args[2],
            self.facts,
        )

    def test_uncertainty_after_repair_skips_visuals(self):
        self.services.verify.side_effect = [
            report(ClaimClassification.CONTRADICTION),
            report(ClaimClassification.UNCERTAIN),
        ]

        result = run_team_pipeline(
            self.request,
            self.services,
            include_visuals=True,
        )

        self.assertEqual(
            result.text.status,
            "needs_review",
        )

        self.assertEqual(
            result.visual_status,
            "skipped_text_needs_review",
        )

        self.services.generate_visual.assert_not_called()

    def test_unchanged_repair_stops_without_rechecking_same_text(self):
        self.services.verify.return_value = report(
            ClaimClassification.CONTRADICTION
        )

        self.services.repair.side_effect = [
            "repaired scene",
            "repaired scene",
        ]

        result = run_team_pipeline(
            self.request,
            self.services,
        )

        self.assertEqual(result.text.status, "needs_review")
        self.assertEqual(result.text.repair_attempts, 2)
        self.assertEqual(self.services.verify.call_count, 2)
        self.assertEqual(result.text.final_scene.revision, 1)

    def test_final_allowed_repair_is_verified(self):
        self.request.max_repair_attempts = 1

        self.services.verify.side_effect = [
            report(ClaimClassification.CONTRADICTION),
            report(ClaimClassification.SUPPORTED),
        ]

        result = run_team_pipeline(
            self.request,
            self.services,
        )

        self.assertEqual(result.text.status, "verified")
        self.assertEqual(self.services.verify.call_count, 2)

    def test_zero_repair_limit_checks_but_does_not_repair(self):
        self.request.max_repair_attempts = 0

        self.services.verify.return_value = report(
            ClaimClassification.CONTRADICTION
        )

        result = run_team_pipeline(
            self.request,
            self.services,
        )

        self.assertEqual(result.text.status, "needs_review")
        self.services.repair.assert_not_called()

    def test_empty_report_is_not_a_pass(self):
        self.services.verify.return_value = VerificationReport()

        result = run_team_pipeline(
            self.request,
            self.services,
            include_visuals=True,
        )

        self.assertEqual(result.text.status, "needs_review")
        self.services.generate_visual.assert_not_called()

    def test_unassessable_visual_fact_is_review_even_without_mismatches(self):
        self.services.check_visual.return_value = self.checks(
            "unable_to_assess"
        )

        result = run_team_pipeline(
            self.request,
            self.services,
            include_visuals=True,
        )

        self.assertTrue(result.visual_report.consistent)
        self.assertEqual(result.visual_status, "needs_review")
        self.services.repair_visual.assert_not_called()

    def test_missing_duplicate_and_unknown_visual_ids_need_review(self):
        cases = (
            [],
            self.checks("match").checks * 2,
            [
                SimpleNamespace(
                    fact_id="invented",
                    status="match",
                    explanation="",
                )
            ],
        )

        for checks in cases:
            with self.subTest(checks=checks):
                self.services.check_visual.return_value = (
                    SimpleNamespace(checks=checks)
                )

                result = run_team_pipeline(
                    self.request,
                    self.services,
                    include_visuals=True,
                )

                self.assertEqual(
                    result.visual_status,
                    "needs_review",
                )

    def test_visual_repair_rechecks_final_asset_and_preserves_text(self):
        self.services.check_visual.side_effect = [
            self.checks("mismatch"),
            self.checks("match"),
        ]

        final = VisualAsset(
            image_path="fixed.png",
            prompt="fix",
        )

        self.services.repair_visual.return_value = (
            SimpleNamespace(
                asset=final,
                report=VisualReport(
                    image_path="fixed.png",
                    consistent=True,
                ),
                attempts=1,
            )
        )

        result = run_team_pipeline(
            self.request,
            self.services,
            include_visuals=True,
        )

        self.assertEqual(
            result.visual_status,
            "no_mismatches_detected",
        )
        self.assertEqual(result.visual_repair_attempts, 1)

        self.services.check_visual.assert_called_with(
            final,
            self.facts,
        )

        self.assertEqual(
            self.services.repair_visual.call_args.kwargs[
                "max_attempts"
            ],
            1,
        )

        self.services.repair.assert_not_called()

    def test_visual_failure_keeps_text_and_hides_provider_error_body(self):
        self.services.generate_visual.side_effect = RuntimeError(
            "private provider details"
        )

        result = run_team_pipeline(
            self.request,
            self.services,
            include_visuals=True,
        )

        self.assertEqual(result.text.status, "verified")
        self.assertEqual(result.visual_status, "error")

        self.assertNotIn(
            "private provider details",
            result.visual_error,
        )

    def test_visuals_are_optional(self):
        result = run_team_pipeline(
            self.request,
            self.services,
        )

        self.assertEqual(
            result.visual_status,
            "not_requested",
        )

        self.services.generate_visual.assert_not_called()

    def test_no_visual_repair_when_budget_is_zero(self):
        self.services.check_visual.return_value = self.checks(
            "mismatch"
        )

        result = run_team_pipeline(
            self.request,
            self.services,
            include_visuals=True,
            max_visual_repairs=0,
        )

        self.assertEqual(
            result.visual_status,
            "needs_review",
        )

        self.services.repair_visual.assert_not_called()

    def test_invalid_limits_are_rejected_before_retrieval(self):
        for limit in (-1, True):
            with self.subTest(limit=limit):
                self.request.max_repair_attempts = limit

                with self.assertRaises(ValueError):
                    run_team_pipeline(
                        self.request,
                        self.services,
                    )

        self.services.retrieve.assert_not_called()


class StoryTests(unittest.TestCase):
    def test_generation_uses_prompt_and_canon(self):
        client = Mock()
        client.generate_text.return_value = "Generated scene."

        facts = [
            CanonFact(
                id="F1",
                subject="Amina",
                predicate="magic_ability",
                object="none",
            )
        ]

        result = AIStoryGenerator(client).generate_scene(
            "At the castle",
            facts,
        )

        self.assertEqual(result, "Generated scene.")

        payload = json.loads(
            client.generate_text.call_args.args[1]
        )

        self.assertEqual(
            payload["request"],
            "At the castle",
        )

        self.assertEqual(
            payload["accepted_canon"][0]["id"],
            "F1",
        )

    def test_repair_sends_confirmed_conflicts_and_preserves_evidence(self):
        client = Mock()
        client.generate_text.return_value = "Fixed."

        assessment = report(
            ClaimClassification.CONTRADICTION
        )

        assessment.claims += report(
            ClaimClassification.UNCERTAIN
        ).claims

        AIStoryGenerator(client).repair_scene(
            "Original.",
            assessment,
            [],
        )

        payload = json.loads(
            client.generate_text.call_args.args[1]
        )

        self.assertEqual(
            len(payload["contradictions"]),
            1,
        )

        self.assertEqual(
            payload["contradictions"][0]["evidence_fact_ids"],
            ["F1"],
        )

        self.assertEqual(
            payload["scene"],
            "Original.",
        )

    def test_uncertain_only_report_does_not_call_repair_model(self):
        client = Mock()

        result = AIStoryGenerator(client).repair_scene(
            "Original.",
            report(ClaimClassification.UNCERTAIN),
            [],
        )

        self.assertEqual(result, "Original.")
        client.generate_text.assert_not_called()

    def test_blank_model_output_is_rejected(self):
        client = Mock()
        client.generate_text.return_value = "   "

        with self.assertRaises(ValueError):
            AIStoryGenerator(client).generate_scene(
                "Amina",
                [],
            )


if __name__ == "__main__":
    unittest.main()