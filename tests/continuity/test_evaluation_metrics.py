# Authored by Faris
import pytest

from evaluation.metrics import LABELS, compute_metrics, evidence_metrics

S, C, V, U = "SUPPORTED", "CONTRADICTION", "VALID_NEW_ADDITION", "UNCERTAIN"


def test_label_order_is_fixed_so_matrix_rows_and_columns_are_readable():
    assert LABELS == [S, C, V, U]


def test_perfect_predictions_score_one_everywhere():
    labels = [S, C, V, U, S, C]

    metrics = compute_metrics(labels, labels)

    assert metrics["accuracy"] == 1.0
    assert metrics["macro_f1"] == 1.0
    assert all(metrics["per_class"][label]["f1"] == 1.0 for label in LABELS)


def test_known_example_gives_hand_computed_scores():
    expected = [S, S, C, C, V, U]
    predicted = [S, C, C, C, U, U]

    metrics = compute_metrics(expected, predicted)

    assert metrics["accuracy"] == pytest.approx(4 / 6)
    per_class = metrics["per_class"]
    assert per_class[S]["precision"] == pytest.approx(1.0)
    assert per_class[S]["recall"] == pytest.approx(0.5)
    assert per_class[S]["f1"] == pytest.approx(2 / 3)
    assert per_class[C]["precision"] == pytest.approx(2 / 3)
    assert per_class[C]["recall"] == pytest.approx(1.0)
    assert per_class[C]["f1"] == pytest.approx(0.8)
    assert per_class[U]["precision"] == pytest.approx(0.5)
    assert per_class[U]["recall"] == pytest.approx(1.0)
    assert metrics["macro_f1"] == pytest.approx((2 / 3 + 0.8 + 0 + 2 / 3) / 4)


def test_a_class_that_is_never_predicted_scores_zero_instead_of_failing():
    metrics = compute_metrics([V, V], [U, U])

    assert metrics["per_class"][V]["precision"] == 0.0
    assert metrics["per_class"][V]["recall"] == 0.0
    assert metrics["per_class"][V]["f1"] == 0.0


def test_support_counts_how_many_claims_were_expected_in_each_class():
    metrics = compute_metrics([S, S, C, V], [S, S, C, V])

    assert {label: metrics["per_class"][label]["support"] for label in LABELS} == {
        S: 2,
        C: 1,
        V: 1,
        U: 0,
    }


def test_confusion_matrix_has_expected_classes_as_rows_and_predicted_as_columns():
    metrics = compute_metrics([S, S, C, C, V, U], [S, C, C, C, U, U])

    assert metrics["confusion_matrix"] == {
        "labels": LABELS,
        "rows_are": "expected",
        "columns_are": "predicted",
        "matrix": [
            [1, 1, 0, 0],  # expected SUPPORTED
            [0, 2, 0, 0],  # expected CONTRADICTION
            [0, 0, 0, 1],  # expected VALID_NEW_ADDITION
            [0, 0, 0, 1],  # expected UNCERTAIN
        ],
    }


def test_unsafe_approvals_count_new_additions_predicted_for_contradictions_or_uncertain_claims():
    metrics = compute_metrics([C, U, S, V], [V, V, V, V])

    assert metrics["safety"]["unsafe_approvals"] == 2


def test_false_contradictions_count_contradictions_predicted_for_other_classes():
    metrics = compute_metrics([S, U, C, V], [C, C, C, V])

    assert metrics["safety"]["false_contradictions"] == 2


def test_unknown_label_is_rejected():
    with pytest.raises(ValueError, match="MAYBE"):
        compute_metrics([S], ["MAYBE"])


def test_mismatched_lengths_are_rejected():
    with pytest.raises(ValueError, match="length"):
        compute_metrics([S, C], [S])


def test_empty_input_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        compute_metrics([], [])


def record(expected, predicted, expected_ids, predicted_ids):
    return {
        "expected": expected,
        "predicted": predicted,
        "expected_evidence_ids": expected_ids,
        "predicted_evidence_ids": predicted_ids,
    }


def test_evidence_is_checked_only_for_correctly_classified_supported_and_contradiction_claims():
    records = [
        record(S, S, ["a"], ["a"]),  # right class, right evidence
        record(C, C, ["b"], ["b", "c"]),  # right class, extra evidence
        record(C, U, ["d"], ["d"]),  # wrong class: not evidence-checked
        record(V, V, [], []),  # no evidence expected
    ]

    result = evidence_metrics(records)

    assert result == {"evaluated": 2, "exact_match": 1, "exact_match_rate": 0.5}


def test_evidence_order_does_not_matter():
    result = evidence_metrics([record(C, C, ["a", "b"], ["b", "a"])])

    assert result["exact_match"] == 1


def test_evidence_rate_is_none_when_nothing_could_be_checked():
    result = evidence_metrics([record(S, U, ["a"], [])])

    assert result == {"evaluated": 0, "exact_match": 0, "exact_match_rate": None}
