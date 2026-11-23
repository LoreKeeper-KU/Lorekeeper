# Authored by Abdullah on 21/11/2026
# Offline tests: no API key or real model calls are needed.

import json
import sys
import types
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from generation_engine.character_creator import (
    CharacterDraft,
    CharacterProfile,
    create_character,
)
from generation_engine.models import DemoRequest
from generation_engine.ui_backend import (
    NoCanonError,
    retrieve_for_request,
    run_ui_request,
)
from shared.schemas import CanonFact


def sample_profile():
    return {
        "name": "Nora",
        "role": "Clockmaker",
        "appearance": "Black hair and brown eyes.",
        "background": "An apprentice from a mountain village.",
        "goal": "Build a clock for her village.",
        "flaw": "Too impatient to ask for help.",
        "attributes": [
            {"predicate": "hair_color", "object": "black"},
            {"predicate": "eye_color", "object": "brown"},
        ],
    }


def fake_client():
    # Return a fixed profile instead of calling the real API.
    client = Mock()
    client.generate_structured.return_value = CharacterProfile(
        **sample_profile()
    )
    return client


class CharacterCreationTests(unittest.TestCase):

    def test_empty_canon_creates_a_draft(self):
        client = fake_client()

        result = create_character("Create Nora.", [], client)

        self.assertIsInstance(result, CharacterDraft)
        self.assertEqual(result.status, "draft")
        self.assertEqual(result.profile.name, "Nora")
        self.assertEqual(result.action, "create_character")

        client.generate_structured.assert_called_once()
        client.generate_text.assert_not_called()

        payload = json.loads(
            client.generate_structured.call_args.args[1]
        )
        self.assertEqual(payload["accepted_canon"], [])
        self.assertEqual(payload["request"], "Create Nora.")

    def test_proposed_facts_have_valid_ids_and_one_subject(self):
        result = create_character("Create Nora.", [], fake_client())

        subjects = {fact.subject for fact in result.proposed_facts}
        ids = [fact.id for fact in result.proposed_facts]

        self.assertEqual(subjects, {result.character_id})
        self.assertEqual(len(ids), len(set(ids)))

        for fact in result.proposed_facts:
            # Proposals remain separate from accepted canon.
            self.assertNotIsInstance(fact, CanonFact)

            # Their fields can be used by the canon approval module.
            CanonFact.model_validate(fact.model_dump())

        self.assertTrue(
            any(
                fact.predicate == "name" and fact.object == "Nora"
                for fact in result.proposed_facts
            )
        )

    def test_existing_canon_is_passed_without_changes(self):
        facts = [
            CanonFact(
                id="fact-001",
                subject="world",
                predicate="technology",
                object="clockwork",
            )
        ]
        original = facts[0].model_dump()
        client = fake_client()

        result = create_character("Create Nora.", facts, client)

        payload = json.loads(
            client.generate_structured.call_args.args[1]
        )

        self.assertEqual(payload["accepted_canon"], [original])
        self.assertEqual(facts[0].model_dump(), original)
        self.assertEqual(len(facts), 1)
        self.assertEqual(result.status, "draft")

    def test_separate_drafts_receive_different_ids(self):
        first = create_character("Create Nora.", [], fake_client())
        second = create_character("Create Nora.", [], fake_client())

        self.assertNotEqual(first.character_id, second.character_id)

    def test_json_preserves_the_draft_and_ids(self):
        draft = create_character("Create Nora.", [], fake_client())

        restored = CharacterDraft.model_validate_json(
            draft.model_dump_json()
        )

        self.assertEqual(restored, draft)

    def test_blank_prompt_stops_before_the_api_call(self):
        client = fake_client()

        with self.assertRaises(ValueError):
            create_character("   ", [], client)

        client.generate_structured.assert_not_called()

    def test_invalid_profile_is_rejected(self):
        for change in (
            {"name": "   "},
            {"goal": ""},
            {"unexpected": "value"},
        ):
            with self.subTest(change=change):
                client = fake_client()
                client.generate_structured.return_value = (
                    sample_profile() | change
                )

                with self.assertRaises(ValidationError):
                    create_character("Create Nora.", [], client)

    def test_duplicate_attributes_are_rejected(self):
        duplicates = [
            {"predicate": "hair_color", "object": "black"},
            {"predicate": "hair_color", "object": "red"},
        ]

        with self.assertRaises(ValidationError):
            CharacterProfile(
                **(sample_profile() | {"attributes": duplicates})
            )


class ActionRoutingTests(unittest.TestCase):

    def test_creation_works_in_all_three_modes(self):
        for mode in ("basic", "rag", "verified"):
            with self.subTest(mode=mode):
                client = fake_client()
                request = DemoRequest(
                    prompt="Create Nora.",
                    mode=mode,
                )

                with (
                    patch(
                        "generation_engine.ui_backend.run_pipeline"
                    ) as scene_runner,
                    patch(
                        "generation_engine.ui_backend.run_team_pipeline"
                    ) as team_runner,
                ):
                    result = run_ui_request(
                        request,
                        [],
                        client,
                        action="create_character",
                    )

                self.assertEqual(result.status, "draft")
                scene_runner.assert_not_called()
                team_runner.assert_not_called()
                client.generate_text.assert_not_called()

    def test_creation_retrieval_allows_empty_canon(self):
        # Replace canon retrieval with a fake empty database response.
        memory = types.ModuleType("canon_memory.memory")
        memory.retrieve_canon = Mock(return_value=[])

        package = types.ModuleType("canon_memory")
        package.memory = memory

        modules = {
            "canon_memory": package,
            "canon_memory.memory": memory,
        }

        with patch.dict(sys.modules, modules):
            request = DemoRequest(prompt="Create Nora.")

            facts = retrieve_for_request(
                request,
                action="create_character",
            )

            self.assertEqual(facts, [])

            # The scene route still requires approved canon.
            with self.assertRaises(NoCanonError):
                retrieve_for_request(
                    request,
                    action="generate_scene",
                )

    def test_canon_based_scenes_reject_empty_canon(self):
        for mode in ("rag", "verified"):
            with self.subTest(mode=mode):
                client = fake_client()
                request = DemoRequest(
                    prompt="Write a scene about Nora.",
                    mode=mode,
                )

                with self.assertRaises(NoCanonError):
                    run_ui_request(request, [], client)

                client.generate_text.assert_not_called()
                client.generate_structured.assert_not_called()

    def test_existing_scene_calls_still_work(self):
        client = fake_client()
        client.generate_text.return_value = "Nora repaired the clock."

        request = DemoRequest(
            prompt="Write a scene about Nora.",
            mode="basic",
        )

        # Without an action argument, the default is scene generation.
        result = run_ui_request(request, [], client)

        self.assertEqual(
            result.text.final_scene.text,
            "Nora repaired the clock.",
        )
        self.assertEqual(result.text.status, "unverified")
        client.generate_structured.assert_not_called()

    def test_unknown_action_is_rejected(self):
        client = fake_client()
        request = DemoRequest(prompt="Create Nora.")

        with self.assertRaises(ValueError):
            run_ui_request(
                request,
                [],
                client,
                action="unknown_action",
            )

        client.generate_structured.assert_not_called()
        client.generate_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()