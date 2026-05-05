"""Accuracy tracking utilities for session-based simulation predictions."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# Single-prediction evaluation
# ---------------------------------------------------------------------------

def evaluate_prediction(predicted_score: float, actual_score: float) -> Dict[str, float | int | str]:
    """Evaluate one prediction.

    Correct if absolute error < 10.
    """
    predicted = float(predicted_score)
    actual = float(actual_score)
    error = abs(predicted - actual)
    is_correct = error < 10

    return {
        "predicted_score": predicted,
        "actual_score": actual,
        "error": error,
        "result": "correct" if is_correct else "wrong",
    }


def evaluate_session_prediction(row: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a session prediction row from the simulation engine.

    Expects keys: predicted_score, actual_score.
    Returns the row enriched with error and result fields.
    """
    predicted = row.get("predicted_score")
    actual = row.get("actual_score")

    if predicted is None or actual is None:
        return {**row, "error": None, "result": None}

    eval_result = evaluate_prediction(float(predicted), float(actual))
    return {
        **row,
        "error": eval_result["error"],
        "result": eval_result["result"],
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def summarize_predictions(rows: Iterable[Dict[str, Optional[float]]]) -> Dict[str, float | int]:
    """Aggregate total/correct/wrong/accuracy across prediction rows."""
    total = 0
    correct = 0
    wrong = 0

    for row in rows:
        predicted = row.get("predicted_score")
        actual = row.get("actual_score")
        if predicted is None or actual is None:
            continue

        eval_row = evaluate_prediction(float(predicted), float(actual))
        total += 1
        if eval_row["result"] == "correct":
            correct += 1
        else:
            wrong += 1

    accuracy = round((correct / total) * 100, 2) if total else 0.0
    return {
        "total_predictions": total,
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy,
    }


def summarize_match(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize predictions for a single simulated match.

    Returns overall stats plus per-innings breakdown.
    """
    overall = summarize_predictions(rows)

    innings_stats: Dict[int, Dict[str, float | int]] = {}
    for row in rows:
        inning = int(row.get("inning", 0))
        if inning not in innings_stats:
            innings_stats[inning] = {"total": 0, "correct": 0, "wrong": 0}

        predicted = row.get("predicted_score")
        actual = row.get("actual_score")
        if predicted is None or actual is None:
            continue

        innings_stats[inning]["total"] += 1
        error = abs(float(predicted) - float(actual))
        if error < 10:
            innings_stats[inning]["correct"] += 1
        else:
            innings_stats[inning]["wrong"] += 1

    return {
        **overall,
        "innings_breakdown": innings_stats,
    }
