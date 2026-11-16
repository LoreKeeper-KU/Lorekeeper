# Authored by Faris
"""Metrics for the four-class continuity benchmark (scikit-learn does the counting)."""

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from shared.schemas import ClaimClassification

# Fixed order: confusion-matrix rows and columns follow it.
LABELS = [
    ClaimClassification.SUPPORTED.value,
    ClaimClassification.CONTRADICTION.value,
    ClaimClassification.VALID_NEW_ADDITION.value,
    ClaimClassification.UNCERTAIN.value,
]

_UNSAFE_TO_APPROVE = {ClaimClassification.CONTRADICTION.value, ClaimClassification.UNCERTAIN.value}


def compute_metrics(expected: list[str], predicted: list[str]) -> dict:
    if not expected and not predicted:
        raise ValueError("cannot compute metrics on empty input")
    if len(expected) != len(predicted):
        raise ValueError(f"length mismatch: {len(expected)} expected vs {len(predicted)} predicted")
    for label in [*expected, *predicted]:
        if label not in LABELS:
            raise ValueError(f"unknown label {label!r}; expected one of {LABELS}")

    precision, recall, f1, support = precision_recall_fscore_support(
        expected, predicted, labels=LABELS, zero_division=0
    )
    per_class = {
        label: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, label in enumerate(LABELS)
    }
    pairs = list(zip(expected, predicted))
    return {
        "n": len(expected),
        "accuracy": float(accuracy_score(expected, predicted)),
        "macro_f1": float(sum(item["f1"] for item in per_class.values()) / len(LABELS)),
        "per_class": per_class,
        "confusion_matrix": {
            "labels": LABELS,
            "rows_are": "expected",
            "columns_are": "predicted",
            "matrix": confusion_matrix(expected, predicted, labels=LABELS).tolist(),
        },
        "safety": {
            # a candidate addition offered where canon forbids it or cannot settle it
            "unsafe_approvals": sum(
                1
                for exp, pred in pairs
                if pred == ClaimClassification.VALID_NEW_ADDITION.value and exp in _UNSAFE_TO_APPROVE
            ),
            # a contradiction raised where none exists
            "false_contradictions": sum(
                1
                for exp, pred in pairs
                if pred == ClaimClassification.CONTRADICTION.value
                and exp != ClaimClassification.CONTRADICTION.value
            ),
        },
    }


def evidence_metrics(records: list[dict]) -> dict:
    """Exact-set match of cited fact IDs, over correctly classified SUPPORTED/CONTRADICTION claims."""
    checked = {ClaimClassification.SUPPORTED.value, ClaimClassification.CONTRADICTION.value}
    evaluated = [r for r in records if r["expected"] in checked and r["predicted"] == r["expected"]]
    exact = sum(
        1 for r in evaluated if set(r["predicted_evidence_ids"]) == set(r["expected_evidence_ids"])
    )
    return {
        "evaluated": len(evaluated),
        "exact_match": exact,
        "exact_match_rate": exact / len(evaluated) if evaluated else None,
    }
