"""Session-based simulation engine for IPL checkpoint predictions.

Simulates historical matches from deliveries.csv and generates
predictions at session checkpoints (6, 10, 15, 20 overs) for each innings.

Each match produces 8 predictions (4 per innings, 2 innings per match).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from inference import SESSION_CHECKPOINTS, predict_session


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def _prepare_deliveries(deliveries_path: Path) -> pd.DataFrame:
    """Load and enrich deliveries data with cumulative stats."""
    if not deliveries_path.exists():
        raise FileNotFoundError(f"Missing deliveries file: {deliveries_path}")

    df = pd.read_csv(deliveries_path, low_memory=False)
    df = _normalize_columns(df)

    # Harmonize column names.
    if "id" in df.columns and "match_id" not in df.columns:
        df = df.rename(columns={"id": "match_id"})
    if "innings" in df.columns and "inning" not in df.columns:
        df = df.rename(columns={"innings": "inning"})

    required = ["match_id", "inning", "batting_team", "bowling_team", "total_runs", "over", "ball"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"deliveries.csv missing required columns: {missing}")

    # Ensure numeric types.
    for col in ["match_id", "inning", "total_runs", "over", "ball", "is_wicket"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "is_wicket" not in df.columns:
        df["is_wicket"] = 0

    df = df.sort_values(["match_id", "inning", "over", "ball"]).reset_index(drop=True)

    # Cumulative runs and wickets per innings.
    df["runs_so_far"] = df.groupby(["match_id", "inning"])["total_runs"].cumsum()
    df["wickets_so_far"] = df.groupby(["match_id", "inning"])["is_wicket"].cumsum().clip(upper=10)

    # Ball position (approximate legal ball count).
    df["ball_position"] = df.apply(
        lambda r: max(int(r["over"]) * 6 + int(r["ball"]), 0), axis=1
    )
    df["overs_float"] = df["ball_position"].apply(
        lambda balls: round((balls // 6) + (balls % 6) / 10, 1)
    )

    return df


def _load_matches(matches_path: Path) -> pd.DataFrame:
    """Load matches data for winner info and metadata."""
    if not matches_path.exists():
        raise FileNotFoundError(f"Missing matches file: {matches_path}")

    df = pd.read_csv(matches_path, low_memory=False)
    df = _normalize_columns(df)

    # Harmonize id column.
    if "match_id" not in df.columns and "id" in df.columns:
        df = df.rename(columns={"id": "match_id"})

    return df


def _get_actual_score_at_checkpoint(innings_df: pd.DataFrame, checkpoint_over: int) -> int:
    """Get the actual cumulative score at a given over checkpoint.

    If the innings ended before this checkpoint, return the final score.
    """
    checkpoint_balls = checkpoint_over * 6
    rows_at_checkpoint = innings_df[innings_df["ball_position"] <= checkpoint_balls]
    if rows_at_checkpoint.empty:
        return 0
    return int(rows_at_checkpoint.iloc[-1]["runs_so_far"])


# ---------------------------------------------------------------------------
# Session simulation
# ---------------------------------------------------------------------------

def _simulate_innings_sessions(innings_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Generate session checkpoint predictions for one innings.

    Produces up to 4 predictions per innings (at 6, 10, 15, 20 overs).
    For each checkpoint:
    - Gather the match state JUST BEFORE the checkpoint
    - Predict the score AT the checkpoint
    - Compare with actual score at that checkpoint
    """
    output: List[Dict[str, Any]] = []
    final_score = int(innings_df["total_runs"].sum())

    match_id = int(innings_df["match_id"].iloc[0])
    inning = int(innings_df["inning"].iloc[0])
    batting_team = str(innings_df["batting_team"].iloc[0])
    bowling_team = str(innings_df["bowling_team"].iloc[0])

    # Max ball position in this innings.
    max_ball_pos = int(innings_df["ball_position"].max())

    for i, target_over in enumerate(SESSION_CHECKPOINTS):
        # Determine the current_over: the state we're predicting FROM.
        if i == 0:
            # First prediction: at match start (0 overs), predict score at 6.
            current_over_val = 0.0
            current_runs = 0
            current_wickets = 0
        else:
            # Predict from the END of the previous checkpoint.
            prev_checkpoint = SESSION_CHECKPOINTS[i - 1]
            prev_checkpoint_balls = prev_checkpoint * 6

            if prev_checkpoint_balls > max_ball_pos:
                # Innings ended before this checkpoint — skip.
                continue

            rows_at_prev = innings_df[innings_df["ball_position"] <= prev_checkpoint_balls]
            if rows_at_prev.empty:
                continue

            latest = rows_at_prev.iloc[-1]
            current_over_val = float(latest["overs_float"])
            current_runs = int(latest["runs_so_far"])
            current_wickets = int(latest["wickets_so_far"])

        # Get actual score at target checkpoint.
        actual_score = _get_actual_score_at_checkpoint(innings_df, target_over)

        # If this is the final checkpoint (20 overs), actual = final innings score.
        if target_over == 20:
            actual_score = final_score

        # Run prediction.
        predicted_score = None
        predicted_winner = None
        win_percentage = None

        try:
            pred = predict_session(
                batting_team=batting_team,
                bowling_team=bowling_team,
                runs=current_runs,
                wickets=current_wickets,
                overs=current_over_val,
                target_over=target_over,
            )
            predicted_score = int(pred.get("predicted_score", 0))
            predicted_winner = pred.get("predicted_winner")
            win_percentage = pred.get("win_percentage")
        except Exception:
            # Keep simulation robust even if a single prediction fails.
            pass

        # Compute error and result.
        error = abs(predicted_score - actual_score) if predicted_score is not None else None
        result = None
        if error is not None:
            result = "correct" if error < 10 else "wrong"

        output.append({
            "match_id": match_id,
            "inning": inning,
            "batting_team": batting_team,
            "bowling_team": bowling_team,
            "current_over": current_over_val,
            "target_over": target_over,
            "current_runs": current_runs if i > 0 else 0,
            "current_wickets": current_wickets if i > 0 else 0,
            "predicted_score": predicted_score,
            "actual_score": actual_score,
            "error": error,
            "result": result,
            "predicted_winner": predicted_winner,
            "win_percentage": win_percentage,
        })

    return output


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_simulation(
    deliveries_path: Path | str = "data/raw/deliveries.csv",
    matches_path: Path | str = "data/raw/matches1.csv",
    save_path: Path | str = "data/processed/simulation_results.csv",
    match_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run session-based checkpoint simulation.

    Args:
        deliveries_path: Path to deliveries CSV.
        matches_path: Path to matches CSV (used for metadata).
        save_path: Where to save results CSV.
        match_id: If provided, simulate only this match. Otherwise all matches.

    Returns:
        List of prediction rows (8 per match: 4 checkpoints × 2 innings).
    """
    deliveries = _prepare_deliveries(Path(deliveries_path))

    # Filter to specific match if requested.
    if match_id is not None:
        deliveries = deliveries[deliveries["match_id"] == match_id]
        if deliveries.empty:
            raise ValueError(f"No deliveries found for match_id={match_id}")

    all_predictions: List[Dict[str, Any]] = []

    for (mid, inn), innings_df in deliveries.groupby(["match_id", "inning"], sort=True):
        predictions = _simulate_innings_sessions(innings_df)
        all_predictions.extend(predictions)

    # Save CSV.
    if save_path:
        save_file = Path(save_path)
        save_file.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(all_predictions).to_csv(save_file, index=False)

    return all_predictions


def get_available_matches(
    matches_path: Path | str = "data/raw/matches1.csv",
) -> List[Dict[str, Any]]:
    """Return all available IPL matches sorted by season then team names.

    Used to populate the training page dropdown.
    """
    df = _load_matches(Path(matches_path))

    required = ["match_id", "team1", "team2"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"matches.csv missing required columns: {missing}")

    # Extract useful fields.
    records = []
    for _, row in df.iterrows():
        season = row.get("season", row.get("date", "unknown"))
        if pd.notna(row.get("date")):
            try:
                season = str(pd.to_datetime(row["date"]).year)
            except Exception:
                season = str(season) if pd.notna(season) else "unknown"
        else:
            season = str(season) if pd.notna(season) else "unknown"

        records.append({
            "match_id": int(row["match_id"]),
            "season": str(season),
            "team1": str(row["team1"]),
            "team2": str(row["team2"]),
            "winner": str(row.get("winner", "")) if pd.notna(row.get("winner")) else "",
            "venue": str(row.get("venue", "")) if pd.notna(row.get("venue")) else "",
            "label": f"{row['team1']} vs {row['team2']} — {season}",
        })

    # Sort by season descending, then team names.
    records.sort(key=lambda r: (r["season"], r["team1"], r["team2"]), reverse=True)
    return records


if __name__ == "__main__":
    # Quick single-match test.
    matches = get_available_matches()
    if matches:
        test_id = matches[0]["match_id"]
        print(f"Simulating match {test_id}: {matches[0]['label']}")
        rows = run_simulation(match_id=test_id)
        print(f"Predictions generated: {len(rows)}")
        for r in rows:
            tag = f"[{r['result']}]" if r["result"] else "[skip]"
            print(
                f"  Inn {r['inning']} | {r['current_over']}->{r['target_over']} ov | "
                f"pred={r['predicted_score']} actual={r['actual_score']} err={r['error']} {tag}"
            )
    else:
        print("No matches found.")
