# Authored by Faris
"""The Streamlit UI, driven with a fake run_pipeline that returns the real result types.

The UI is built against generation_engine.orchestrator.run_pipeline only, so these tests
inject their own pipeline results instead of depending on what the current mock returns.
"""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from generation_engine.models import DemoRequest, PipelineResult, Scene
from shared.schemas import ClaimAssessment, ClaimClassification, VerificationReport

APP = Path(__file__).resolve().parents[2] / "app.py"

ORIGINAL = "Princess Amina stood on the walls. She summoned a magical firestorm."
REPAIRED = "Princess Amina stood on the walls. She commanded her archers."


def assessment(claim, classification, reason, evidence=()):
    return ClaimAssessment(
        claim=claim,
        classification=classification,
        reason=reason,
        evidence_fact_ids=list(evidence),
    )


CONTRADICTION = assessment(
    "Amina summons a magical firestorm.",
    ClaimClassification.CONTRADICTION,
    "Canon states that Amina has no magical ability.",
    ["fact-001"],
)
SUPPORTED = assessment(
    "Amina commands archers.",
    ClaimClassification.SUPPORTED,
    "Canon establishes that Amina commands archers.",
    ["fact-003", "fact-004"],
)
NEW_ADDITION = assessment(
    "The wall is made of white stone.",
    ClaimClassification.VALID_NEW_ADDITION,
    "Nothing in canon rules this out.",
)
UNCERTAIN = assessment(
    "The attackers came from the sea.",
    ClaimClassification.UNCERTAIN,
    "Canon neither supports nor contradicts this.",
)


def result(reports, status="verified", repairs=1, final=REPAIRED):
    return PipelineResult(
        status=status,
        initial_scene=Scene(scene_id="scene_001", text=ORIGINAL, revision=0),
        final_scene=Scene(scene_id="scene_001", text=final, revision=repairs),
        reports=[VerificationReport(claims=claims) for claims in reports],
        repair_attempts=repairs,
    )


class FakePipeline:
    """Stands in for run_pipeline and records the requests it receives."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def launch(monkeypatch):
    """Start the app with a fake pipeline; returns (AppTest, FakePipeline)."""

    def start(outcome):
        fake = FakePipeline(outcome)
        monkeypatch.setattr("generation_engine.orchestrator.run_pipeline", fake)
        return AppTest.from_file(str(APP), default_timeout=10).run(), fake

    return start


def run_it(at):
    return at.button(key="run").click().run()


def markdown_text(at):
    return "\n".join(element.value for element in at.markdown)


def page_text(at):
    """Every piece of text the page shows through markdown, headings and captions."""
    elements = [*at.markdown, *at.subheader, *at.header, *at.caption]
    return "\n".join(element.value for element in elements)


def badge_colours(at):
    """Map each classification badge's label to its colour, e.g. {"SUPPORTED": "green"}."""
    found = re.findall(r":(\w+)-badge\[\S+ ([A-Z_]+)\]", markdown_text(at))
    return {label: colour for colour, label in found}


def metrics(at):
    return {metric.label: metric.value for metric in at.metric}


def test_page_shows_the_header_and_inputs_before_anything_is_run(launch):
    at, fake = launch(result([[SUPPORTED]]))

    assert not at.exception
    assert "LoreKeeper" in at.title[0].value
    assert at.text_area(key="concept").value.strip() != ""
    assert at.selectbox(key="mode").value == "verified"
    assert len(at.selectbox(key="mode").options) == 3
    assert at.button(key="run") is not None
    assert fake.requests == []
    assert not at.subheader


def test_run_sends_the_concept_mode_and_repair_limit_to_the_pipeline(launch):
    at, fake = launch(result([[SUPPORTED]]))

    at.text_area(key="concept").set_value("A thief steals the crown.")
    at.selectbox(key="mode").select("rag")
    at.slider(key="max_repairs").set_value(2)
    run_it(at)

    assert fake.requests == [
        DemoRequest(prompt="A thief steals the crown.", mode="rag", max_repair_attempts=2)
    ]


def test_an_empty_concept_is_not_sent_to_the_pipeline(launch):
    at, fake = launch(result([[SUPPORTED]]))

    at.text_area(key="concept").set_value("   ")
    run_it(at)

    assert fake.requests == []
    assert any("concept" in warning.value.lower() for warning in at.warning)


def test_original_and_final_scenes_are_both_shown(launch):
    at, _ = launch(result([[CONTRADICTION], [SUPPORTED]]))
    run_it(at)

    text = markdown_text(at)
    assert ORIGINAL in text
    assert REPAIRED in text


def test_each_claim_shows_its_text_classification_reason_and_evidence_ids(launch):
    at, _ = launch(result([[CONTRADICTION, SUPPORTED, NEW_ADDITION, UNCERTAIN]]))
    run_it(at)

    text = markdown_text(at)
    for item in (CONTRADICTION, SUPPORTED, NEW_ADDITION, UNCERTAIN):
        assert item.claim in text
        assert item.reason in text
        assert item.classification.value in text
    for fact_id in ("fact-001", "fact-003", "fact-004"):
        assert fact_id in text
    assert "none cited" in text  # the claims that cite no evidence say so


def test_the_four_classifications_have_four_different_colours(launch):
    at, _ = launch(result([[CONTRADICTION, SUPPORTED, NEW_ADDITION, UNCERTAIN]]))
    run_it(at)

    colours = badge_colours(at)
    assert set(colours) == {"SUPPORTED", "CONTRADICTION", "VALID_NEW_ADDITION", "UNCERTAIN"}
    assert len(set(colours.values())) == 4


def test_every_verification_pass_is_listed_with_its_own_summary_counts(launch):
    at, _ = launch(result([[CONTRADICTION, UNCERTAIN], [SUPPORTED]]))
    run_it(at)

    text = page_text(at)
    assert "Pass 1" in text and "Pass 2" in text
    assert [m.value for m in at.metric if m.label == "Contradictions"] == ["1", "0"]
    assert [m.value for m in at.metric if m.label == "Supported"] == ["0", "1"]


def test_status_and_repair_attempts_are_shown(launch):
    at, _ = launch(result([[CONTRADICTION]], status="needs_review", repairs=3))
    run_it(at)

    assert "Needs review" in markdown_text(at)
    assert metrics(at)["Repair attempts"] == "3"


def test_modes_that_skip_verification_say_so_instead_of_showing_claims(launch):
    at, _ = launch(result([], status="unverified", repairs=0, final=ORIGINAL))
    run_it(at)

    assert any("not run" in info.value.lower() for info in at.info)
    assert "Unverified" in markdown_text(at)
    assert not [m for m in at.metric if m.label == "Contradictions"]


def test_a_pipeline_error_is_shown_without_crashing_the_page(launch):
    at, _ = launch(RuntimeError("No verifier is configured."))
    run_it(at)

    assert not at.exception
    assert any("No verifier is configured." in error.value for error in at.error)


def test_results_stay_on_screen_when_another_widget_changes(launch):
    at, fake = launch(result([[SUPPORTED]]))
    run_it(at)

    at.slider(key="max_repairs").set_value(1).run()

    assert SUPPORTED.claim in markdown_text(at)
    assert len(fake.requests) == 1
