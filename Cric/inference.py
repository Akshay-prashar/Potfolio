"""Inference utilities for live IPL prediction with session-based checkpoints."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np


# ---------------------------------------------------------------------------
# Session checkpoint constants
# ---------------------------------------------------------------------------
SESSION_CHECKPOINTS: Tuple[int, ...] = (6, 10, 15, 20)

MODELS_DIR = Path("models")
WINNER_MODEL_PATH = MODELS_DIR / "winner_model.pkl"
SCORE_MODEL_PATH = MODELS_DIR / "score_model.pkl"
PREPROCESSOR_PATH = MODELS_DIR / "preprocessing_objects.pkl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_next_checkpoint(current_overs: float) -> int:
    """Return the next session checkpoint over based on current progress.

    >>> get_next_checkpoint(2.3)
    6
    >>> get_next_checkpoint(6.0)
    10
    >>> get_next_checkpoint(14.5)
    15
    >>> get_next_checkpoint(15.0)
    20
    """
    for checkpoint in SESSION_CHECKPOINTS:
        if current_overs < checkpoint:
            return checkpoint
    return SESSION_CHECKPOINTS[-1]


def _overs_to_balls(overs: float) -> int:
    """Convert cricket over notation to total balls bowled.

    Example:
    - 5.2 -> 32 balls
    - 10.0 -> 60 balls
    """
    if overs < 0:
        raise ValueError("overs must be non-negative")

    whole_overs = int(overs)
    partial_balls = int(round((overs - whole_overs) * 10))
    if partial_balls > 5:
        raise ValueError("Invalid overs format: decimal part must be between 0 and 5.")
    return (whole_overs * 6) + partial_balls


def _build_class_mapping(classes: List[str]) -> Dict[str, int]:
    """Build string-to-index mapping from saved encoder classes."""
    return {str(name): idx for idx, name in enumerate(classes)}


def _canonical_team_name(name: str) -> str:
    """Create a canonical team key for fuzzy team-name matching."""
    return str(name).strip().lower().replace("&", "and").replace("-", " ").replace("_", " ")


def _resolve_team_name(input_name: str, mapping: Dict[str, int]) -> str:
    """Resolve user/scraper team name to an exact training-class name."""
    if input_name in mapping:
        return input_name

    canonical_input = _canonical_team_name(input_name)
    if canonical_input in mapping:
        return canonical_input

    reverse_lookup = {_canonical_team_name(k): k for k in mapping}
    if canonical_input in reverse_lookup:
        return reverse_lookup[canonical_input]

    # Common IPL aliases.
    aliases = {
        "mi": "Mumbai Indians",
        "csk": "Chennai Super Kings",
        "rcb": "Royal Challengers Bengaluru",
        "royal challengers bangalore": "Royal Challengers Bengaluru",
        "dc": "Delhi Capitals",
        "dd": "Delhi Capitals",
        "kkr": "Kolkata Knight Riders",
        "srh": "Sunrisers Hyderabad",
        "pk": "Punjab Kings",
        "kings xi punjab": "Punjab Kings",
        "rr": "Rajasthan Royals",
        "gt": "Gujarat Titans",
        "lsg": "Lucknow Super Giants",
    }
    expanded = aliases.get(canonical_input, canonical_input)
    if expanded in mapping:
        return expanded
    if expanded in reverse_lookup:
        return reverse_lookup[expanded]

    raise ValueError(f"Unknown team '{input_name}' not present in preprocessing classes.")


def _display_team_name(name: str) -> str:
    """Convert canonical/team-key name into readable title-case format."""
    return str(name).replace("_", " ").strip().title()


def _winner_from_probability(
    batting_team: str,
    bowling_team: str,
    batting_win_probability: float,
) -> Dict[str, Any]:
    """Decide likely winner and percentage.

    Rules:
    - If prob < 0.5 -> bowling team likely winner, use 1 - prob
    - If prob >= 0.5 -> batting team likely winner
    """
    batting_prob = min(max(float(batting_win_probability), 0.0), 1.0)
    if batting_prob < 0.5:
        winner = bowling_team
        win_prob = 1.0 - batting_prob
    else:
        winner = batting_team
        win_prob = batting_prob

    win_pct_int = int(round(win_prob * 100))
    return {
        "predicted_winner": _display_team_name(winner),
        "win_percentage": f"{win_pct_int}%",
        "win_probability": win_prob,
    }


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_artifacts() -> Dict[str, Any]:
    """Load models and preprocessing data once per process."""
    for path in [WINNER_MODEL_PATH, SCORE_MODEL_PATH, PREPROCESSOR_PATH]:
        if not path.exists():
            raise FileNotFoundError(f"Missing required artifact: {path}")

    winner_model = joblib.load(WINNER_MODEL_PATH)
    score_model = joblib.load(SCORE_MODEL_PATH)
    preprocessing = joblib.load(PREPROCESSOR_PATH)

    batting_classes = preprocessing.get("batting_encoder_classes")
    bowling_classes = preprocessing.get("bowling_encoder_classes")
    winner_classes = preprocessing.get("winner_encoder_classes")
    winner_feature_cols = preprocessing.get("winner_feature_cols")
    score_feature_cols = preprocessing.get("score_feature_cols")

    if not batting_classes or not bowling_classes:
        raise ValueError("preprocessing_objects.pkl is missing team encoder class lists.")

    if not winner_feature_cols:
        # Fallback to the expected Colab training feature order.
        winner_feature_cols = [
            "batting_team_enc",
            "bowling_team_enc",
            "runs",
            "wickets",
            "overs",
            "balls_left",
            "current_run_rate",
        ]
        score_feature_cols = winner_feature_cols.copy()

    return {
        "winner_model": winner_model,
        "score_model": score_model,
        "winner_feature_cols": winner_feature_cols,
        "score_feature_cols": score_feature_cols,
        "batting_map": _build_class_mapping(batting_classes),
        "bowling_map": _build_class_mapping(bowling_classes),
        "winner_classes": [str(x) for x in winner_classes] if winner_classes else None,
    }


# ---------------------------------------------------------------------------
# Session-based prediction (NEW — core feature)
# ---------------------------------------------------------------------------

def predict_session(
    batting_team: str,
    bowling_team: str,
    runs: int | float,
    wickets: int | float,
    overs: int | float,
    target_over: int | None = None,
    inning: int = 1,
    target_runs: float = 0,
) -> Dict[str, Any]:
    """Predict score at a specific session checkpoint.

    This is the primary prediction function for the session-based system.
    It predicts what the score will be at `target_over` given the current
    match state.

    If target_over is None, the next checkpoint is auto-detected.

    Steps:
    1. Load models and preprocessing objects
    2. Resolve team names and validate inputs
    3. Build feature array for current state
    4. Use score model to get trajectory-based prediction
    5. Project score to the target checkpoint using run-rate scaling
    6. Predict winner probabilities
    """
    artifacts = _load_artifacts()
    winner_model = artifacts["winner_model"]
    score_model = artifacts["score_model"]

    # Resolve teams.
    batting_raw = str(batting_team).strip()
    bowling_raw = str(bowling_team).strip()
    batting_name = _resolve_team_name(batting_raw, artifacts["batting_map"])
    bowling_name = _resolve_team_name(bowling_raw, artifacts["bowling_map"])

    # Validate inputs.
    runs_val = float(runs)
    wickets_val = float(wickets)
    overs_val = float(overs)

    if runs_val < 0:
        raise ValueError("runs must be non-negative")
    if wickets_val < 0 or wickets_val > 10:
        raise ValueError("wickets must be in range [0, 10]")

    # Determine target checkpoint.
    if target_over is None:
        target_over = get_next_checkpoint(overs_val)
    target_over = int(target_over)

    # Convert overs to balls.
    balls_bowled = _overs_to_balls(overs_val)
    balls_in_innings = 120  # 20 overs
    balls_left = max(balls_in_innings - balls_bowled, 0)
    current_run_rate = (runs_val * 6.0 / balls_bowled) if balls_bowled > 0 else 0.0

    required_run_rate = 0.0
    if inning == 2 and balls_left > 0:
        required_run_rate = ((target_runs - runs_val) * 6.0) / balls_left
        required_run_rate = max(0.0, min(required_run_rate, 36.0))

    # Build feature vector for current state.
    feature_values = {
        "batting_team_enc": artifacts["batting_map"][batting_name],
        "bowling_team_enc": artifacts["bowling_map"][bowling_name],
        "runs": runs_val,  # Fallback compat
        "wickets": wickets_val,  # Fallback compat
        "overs": overs_val,  # Fallback compat
        "current_runs": runs_val,
        "current_wickets": wickets_val,
        "balls_left": float(balls_left),
        "current_run_rate": float(current_run_rate),
        "inning": inning,
        "target_runs": float(target_runs),
        "required_run_rate": float(required_run_rate),
    }

    winner_ordered = [feature_values[col] for col in artifacts["winner_feature_cols"]]
    score_ordered = [feature_values[col] for col in artifacts["score_feature_cols"]]
    
    x_win = np.array([winner_ordered], dtype=float)
    x_score = np.array([score_ordered], dtype=float)

    # Model predictions.
    predicted_final_score = float(score_model.predict(x_score)[0])
    winner_proba = winner_model.predict_proba(x_win)[0]

    # --- Session score projection ---
    # The model predicts a 20-over final score from current trajectory.
    # We project to the target checkpoint using run-rate scaling.
    target_balls = target_over * 6
    if balls_bowled >= target_balls:
        # Already past this checkpoint — predicted score IS current runs.
        predicted_checkpoint_score = int(round(runs_val))
    elif balls_bowled > 0:
        # Project using weighted blend of model prediction and run-rate.
        # Model's projected final score scaled to checkpoint proportion.
        model_projection = predicted_final_score * (target_over / 20.0)
        # Run-rate-based linear projection.
        remaining_to_checkpoint = target_balls - balls_bowled
        rr_projection = runs_val + (current_run_rate * remaining_to_checkpoint / 6.0)
        # Wicket-decay factor: more wickets = lower projection.
        wicket_factor = max(1.0 - (wickets_val * 0.04), 0.5)
        rr_projection *= wicket_factor
        # Blend: heavier on model early, heavier on run-rate when closer.
        progress = balls_bowled / target_balls  # 0..1
        blend_weight = min(progress, 0.7)  # cap model influence
        predicted_checkpoint_score = int(round(
            (1 - blend_weight) * model_projection + blend_weight * rr_projection
        ))
    else:
        # No balls bowled yet — pure model projection.
        predicted_checkpoint_score = int(round(predicted_final_score * (target_over / 20.0)))

    # Ensure predicted score is at least current runs.
    predicted_checkpoint_score = max(predicted_checkpoint_score, int(round(runs_val)))

    # --- Winner probability ---
    winner_classes = artifacts["winner_classes"]
    if winner_classes and len(winner_classes) == len(winner_proba):
        class_probabilities = {
            winner_classes[idx]: float(prob) for idx, prob in enumerate(winner_proba)
        }
    else:
        class_probabilities = {f"class_{idx}": float(prob) for idx, prob in enumerate(winner_proba)}

    batting_win_probability = class_probabilities.get(batting_name)
    if batting_win_probability is None:
        bowling_probability = class_probabilities.get(bowling_name)
        if bowling_probability is not None:
            batting_win_probability = 1.0 - float(bowling_probability)
        else:
            batting_win_probability = float(max(winner_proba))

    winner_summary = _winner_from_probability(
        batting_team=batting_name,
        bowling_team=bowling_name,
        batting_win_probability=float(batting_win_probability),
    )

    return {
        "batting_team": _display_team_name(batting_name),
        "bowling_team": _display_team_name(bowling_name),
        "current_runs": int(round(runs_val)),
        "wickets": int(round(wickets_val)),
        "overs": overs_val,
        "target_over": target_over,
        "predicted_score": predicted_checkpoint_score,
        "predicted_winner": winner_summary["predicted_winner"],
        "win_percentage": winner_summary["win_percentage"],
        "win_probability": winner_summary["win_probability"],
        "current_run_rate": round(current_run_rate, 2),
        "balls_bowled": balls_bowled,
        "balls_left": balls_left,
    }


# ---------------------------------------------------------------------------
# Legacy predict_live (backward-compatible wrapper)
# ---------------------------------------------------------------------------

def predict_live(
    batting_team: str,
    bowling_team: str,
    runs: int | float,
    wickets: int | float,
    overs: int | float,
) -> Dict[str, Any]:
    """Predict live win probability and final score.

    This is the backward-compatible wrapper. Internally delegates to
    predict_session with auto-detected target_over.
    """
    session = predict_session(
        batting_team=batting_team,
        bowling_team=bowling_team,
        runs=runs,
        wickets=wickets,
        overs=overs,
        target_over=None,
    )

    # Build legacy-compatible output format.
    overs_val = float(overs)
    balls_bowled = session["balls_bowled"]
    balls_left = session["balls_left"]
    current_run_rate = session["current_run_rate"]
    target_over = session["target_over"]

    result = {
        "predicted_winner": session["predicted_winner"],
        "win_percentage": session["win_percentage"],
        "predicted_score": session["predicted_score"],
        "target_over": target_over,
        "inputs": {
            "batting_team": session["batting_team"],
            "bowling_team": session["bowling_team"],
            "runs": float(runs),
            "wickets": float(wickets),
            "overs": overs_val,
            "balls_bowled": balls_bowled,
        },
        "derived_features": {
            "balls_left": balls_left,
            "current_run_rate": current_run_rate,
        },
        "predictions": {
            "predicted_score": session["predicted_score"],
            "predicted_winner": session["predicted_winner"],
            "win_percentage": session["win_percentage"],
            "target_over": target_over,
            "batting_team_win_probability": session["win_probability"],
        },
    }
    return result


if __name__ == "__main__":
    # Example usage for quick manual testing.
    sample = predict_session(
        batting_team="Mumbai Indians",
        bowling_team="Chennai Super Kings",
        runs=78,
        wickets=2,
        overs=9.4,
    )
    print(f"Target Over: {sample['target_over']}")
    print(f"Predicted Score at {sample['target_over']} overs: {sample['predicted_score']}")
    print(f"Predicted Winner: {sample['predicted_winner']} ({sample['win_percentage']})")
    print()

    # Test all checkpoints.
    for cp in SESSION_CHECKPOINTS:
        s = predict_session(
            batting_team="Mumbai Indians",
            bowling_team="Chennai Super Kings",
            runs=45,
            wickets=1,
            overs=5.0,
            target_over=cp,
        )
        print(f"  At 5.0 overs -> predict {cp} overs: {s['predicted_score']} runs")
