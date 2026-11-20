# Authored by Faris
"""Presentation rules: how a PipelineResult is summarised for display. No Streamlit involved."""

from lorekeeper_ui.presentation import (
    canon_check,
    claim_repair_state,
    classification_label,
    classification_slug,
    find_image,
    repair_steps,
    session_title,
)
from ui_builders import (
    CONTRADICTION,
    ORIGINAL,
    OTHER_CONTRADICTION,
    REPAIRED,
    SUPPORTED,
    UNCERTAIN,
    result,
)


# ---- the compact "Canon Check" headline ----

def test_a_clean_scene_reads_verified():
    check = canon_check(result([[SUPPORTED]], repairs=0, final=ORIGINAL))

    assert (check.headline, check.tone, check.repaired) == ("Verified", "verified", False)


def test_a_repaired_scene_says_what_was_found_and_repaired():
    check = canon_check(result([[CONTRADICTION], [SUPPORTED]]))

    assert check.headline == "1 contradiction detected and repaired"
    assert (check.tone, check.repaired) == ("verified", True)


def test_the_headline_pluralises_by_the_contradictions_in_the_original_scene():
    check = canon_check(result([[CONTRADICTION, OTHER_CONTRADICTION], [SUPPORTED]]))

    assert check.headline == "2 contradictions detected and repaired"


def test_contradictions_left_after_repair_attempts_need_review():
    check = canon_check(
        result([[CONTRADICTION], [CONTRADICTION]], status="needs_review", repairs=3)
    )

    assert check.headline == "1 contradiction remains after 3 repair attempts — needs review"
    assert check.tone == "review"


def test_contradictions_with_no_repair_attempts_need_review():
    check = canon_check(
        result([[CONTRADICTION]], status="needs_review", repairs=0, final=ORIGINAL)
    )

    assert check.headline == "1 contradiction remains — needs review"


def test_uncertain_claims_need_review():
    one = canon_check(
        result([[SUPPORTED, UNCERTAIN]], status="needs_review", repairs=0, final=ORIGINAL)
    )
    two = canon_check(
        result([[UNCERTAIN, UNCERTAIN]], status="needs_review", repairs=0, final=ORIGINAL)
    )

    assert one.headline == "1 uncertain claim needs review"
    assert two.headline == "2 uncertain claims need review"
    assert one.tone == "review"


def test_a_repaired_contradiction_is_still_mentioned_when_uncertainty_remains():
    check = canon_check(result([[CONTRADICTION], [UNCERTAIN]], status="needs_review"))

    assert check.headline == "1 contradiction repaired · 1 uncertain claim needs review"


def test_a_report_with_no_claims_cannot_confirm_consistency():
    check = canon_check(result([[]], status="needs_review", repairs=0, final=ORIGINAL))

    assert check.headline == "No checkable claims were found — needs review"


def test_modes_without_verification_are_marked_as_not_run():
    check = canon_check(result([], status="unverified", repairs=0, final=ORIGINAL))

    assert (check.headline, check.tone) == ("Not run in this mode", "skipped")


def test_an_error_status_is_reported_as_an_error():
    check = canon_check(result([[]], status="error", repairs=0, final=ORIGINAL))

    assert (check.headline, check.tone) == ("Verification could not complete", "error")


def test_an_unknown_status_falls_back_to_review_with_the_raw_status():
    check = canon_check(result([[SUPPORTED]], status="paused", repairs=0, final=ORIGINAL))

    assert (check.headline, check.tone) == ("Status: paused", "review")


# ---- the repair progression ----

def labels(steps):
    return [step.label for step in steps]


def states(steps):
    return [step.state for step in steps]


def test_a_successful_repair_shows_the_full_progression():
    steps = repair_steps(result([[CONTRADICTION], [SUPPORTED]]))

    assert labels(steps) == [
        "Original generation",
        "Canon check found 1 contradiction",
        "Repair performed",
        "Rechecked",
        "Canon verified",
    ]
    assert states(steps) == ["done", "alert", "done", "done", "done"]


def test_several_repair_attempts_are_counted_in_one_step():
    steps = repair_steps(result([[CONTRADICTION], [CONTRADICTION], [SUPPORTED]], repairs=2))

    assert "Repair performed (2 attempts)" in labels(steps)


def test_a_failed_repair_ends_in_needs_review():
    steps = repair_steps(
        result([[CONTRADICTION], [CONTRADICTION]], status="needs_review", repairs=1)
    )

    assert labels(steps)[-2:] == ["Rechecked", "Needs review"]
    assert states(steps)[-1] == "review"


def test_with_no_repair_attempts_the_progression_goes_straight_to_review():
    steps = repair_steps(
        result([[CONTRADICTION]], status="needs_review", repairs=0, final=ORIGINAL)
    )

    assert labels(steps) == [
        "Original generation",
        "Canon check found 1 contradiction",
        "Needs review",
    ]


def test_a_repair_that_changed_nothing_is_not_called_performed_or_rechecked():
    steps = repair_steps(
        result([[CONTRADICTION]], status="needs_review", repairs=1, final=ORIGINAL)
    )

    assert labels(steps) == [
        "Original generation",
        "Canon check found 1 contradiction",
        "Repair attempted (no change)",
        "Needs review",
    ]


def test_there_is_no_progression_when_nothing_needed_repair():
    assert repair_steps(result([[SUPPORTED]], repairs=0, final=ORIGINAL)) == []
    assert repair_steps(result([], status="unverified", repairs=0, final=ORIGINAL)) == []


# ---- the repaired status of one claim ----

def test_a_contradiction_that_vanishes_in_a_later_pass_is_repaired():
    outcome = result([[CONTRADICTION], [SUPPORTED]])

    assert claim_repair_state(outcome, 0, CONTRADICTION) == "repaired"


def test_a_contradiction_that_persists_is_unresolved():
    outcome = result([[CONTRADICTION], [CONTRADICTION]], status="needs_review")

    assert claim_repair_state(outcome, 0, CONTRADICTION) == "unresolved"
    assert claim_repair_state(outcome, 1, CONTRADICTION) == "unresolved"


def test_a_contradiction_in_the_only_pass_is_unresolved():
    outcome = result([[CONTRADICTION]], status="needs_review", repairs=0, final=ORIGINAL)

    assert claim_repair_state(outcome, 0, CONTRADICTION) == "unresolved"


def test_other_classifications_have_no_repair_state():
    outcome = result([[CONTRADICTION, SUPPORTED], [SUPPORTED]])

    assert claim_repair_state(outcome, 0, SUPPORTED) is None


# ---- artwork, classification names and sidebar titles ----

def test_an_existing_image_file_is_found(tmp_path):
    picture = tmp_path / "scene.png"
    picture.write_bytes(b"\x89PNG")
    outcome = result([[SUPPORTED]])
    outcome.image_path = str(picture)

    assert find_image(outcome) == str(picture)


def test_no_image_is_reported_for_a_missing_file_an_empty_path_or_no_attribute(tmp_path):
    outcome = result([[SUPPORTED]])
    assert find_image(outcome) is None

    outcome.image_path = str(tmp_path / "missing.png")
    assert find_image(outcome) is None

    outcome.image_path = ""
    assert find_image(outcome) is None


def test_an_image_url_is_accepted():
    outcome = result([[SUPPORTED]])
    outcome.image_path = "https://example.com/scene.png"

    assert find_image(outcome) == "https://example.com/scene.png"


def test_classifications_are_shown_in_words_with_a_css_friendly_slug():
    assert classification_label("VALID_NEW_ADDITION") == "VALID NEW ADDITION"
    assert classification_label("SUPPORTED") == "SUPPORTED"
    assert classification_slug("VALID_NEW_ADDITION") == "valid-new-addition"


def test_session_titles_are_short_single_line_versions_of_the_prompt():
    assert session_title("Write the next scene") == "Write the next scene"
    assert session_title("  Write\n the   next   scene ") == "Write the next scene"
    long_title = session_title("a" * 100, limit=20)
    assert len(long_title) == 20 and long_title.endswith("…")
