"""Feature engineering utilities for pre-match and live models."""

from typing import Dict

import numpy as np
import pandas as pd


def build_prematch_features(matches_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build match-level features for pre-match winner prediction.

    Output is numeric and model-ready for XGBoost training.
    """
    df = matches_df.copy()

    required = {"team1", "team2"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"matches dataframe missing required columns: {sorted(missing)}")

    if "id" not in df.columns:
        df["id"] = np.arange(1, len(df) + 1, dtype=int)

    has_target = "winner" in df.columns
    if has_target:
        # Keep only completed matches with known winners during training.
        df["winner"] = df["winner"].fillna("unknown").astype(str)
        df = df[df["winner"] != "unknown"].copy()

    if "season" not in df.columns:
        df["season"] = 0
    if "toss_winner" not in df.columns:
        df["toss_winner"] = "unknown"
    if "toss_decision" not in df.columns:
        df["toss_decision"] = "unknown"
    if "venue" not in df.columns:
        df["venue"] = "unknown"
    if "city" not in df.columns:
        df["city"] = "unknown"

    df["team1_id"] = pd.Categorical(df["team1"]).codes
    df["team2_id"] = pd.Categorical(df["team2"]).codes
    df["toss_winner_id"] = pd.Categorical(df["toss_winner"]).codes
    df["venue_id"] = pd.Categorical(df["venue"]).codes
    df["city_id"] = pd.Categorical(df["city"]).codes
    df["toss_decision_bat"] = (df["toss_decision"].astype(str).str.lower() == "bat").astype(int)

    feature_cols = [
        "id",
        "season",
        "team1_id",
        "team2_id",
        "toss_winner_id",
        "toss_decision_bat",
        "venue_id",
        "city_id",
    ]
    if has_target:
        # Binary target: did team1 win?
        df["team1_won"] = (df["winner"] == df["team1"]).astype(int)
        feature_cols.append("team1_won")
    return df[feature_cols].copy()


def build_ball_by_ball_features(deliveries_df: pd.DataFrame, matches_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build ball-level and live-state features for each innings snapshot.

    Includes required live fields:
    runs, wickets, overs, balls_left, current_run_rate, required_run_rate.
    """
    df = deliveries_df.copy()

    required = {"match_id", "inning", "batting_team", "bowling_team", "total_runs"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"deliveries dataframe missing required columns: {sorted(missing)}")

    if "over" not in df.columns:
        df["over"] = 0
    if "ball" not in df.columns:
        df["ball"] = 0
    if "wide_runs" not in df.columns:
        df["wide_runs"] = 0
    if "noball_runs" not in df.columns:
        df["noball_runs"] = 0
    if "dismissal_kind" not in df.columns:
        df["dismissal_kind"] = "none"
    if "player_dismissed" not in df.columns:
        df["player_dismissed"] = ""

    sort_cols = ["match_id", "inning", "over", "ball"]
    df = df.sort_values(sort_cols).reset_index(drop=True)

    # Track legal balls (wides/no-balls do not consume a legal delivery).
    df["is_legal_delivery"] = (
        (df["wide_runs"].fillna(0).astype(float) == 0)
        & (df["noball_runs"].fillna(0).astype(float) == 0)
    ).astype(int)

    df["balls_bowled"] = df.groupby(["match_id", "inning"])["is_legal_delivery"].cumsum()
    df["runs"] = df.groupby(["match_id", "inning"])["total_runs"].cumsum()

    dismissal_kind = df["dismissal_kind"].fillna("none").astype(str).str.lower()
    player_dismissed = df["player_dismissed"].fillna("").astype(str).str.strip()
    df["wicket_fell"] = ((player_dismissed != "") & (dismissal_kind != "retired hurt")).astype(int)
    df["wickets"] = df.groupby(["match_id", "inning"])["wicket_fell"].cumsum()

    innings_balls = 120
    df["overs"] = df["balls_bowled"] / 6.0
    df["balls_left"] = (innings_balls - df["balls_bowled"]).clip(lower=0)

    df["current_run_rate"] = np.where(
        df["balls_bowled"] > 0,
        (df["runs"] * 6.0) / df["balls_bowled"],
        0.0,
    )

    first_innings_totals = (
        df[df["inning"] == 1]
        .groupby("match_id", as_index=False)["total_runs"]
        .sum()
        .rename(columns={"total_runs": "first_innings_score"})
    )
    df = df.merge(first_innings_totals, on="match_id", how="left")
    df["target"] = np.where(df["inning"] == 2, df["first_innings_score"] + 1, np.nan)
    df["runs_remaining"] = np.where(df["inning"] == 2, (df["target"] - df["runs"]).clip(lower=0), np.nan)

    df["required_run_rate"] = np.where(
        (df["inning"] == 2) & (df["balls_left"] > 0),
        (df["runs_remaining"] * 6.0) / df["balls_left"],
        0.0,
    )

    # Final score per innings is a useful training target for score prediction.
    innings_totals = (
        df.groupby(["match_id", "inning"], as_index=False)["total_runs"]
        .sum()
        .rename(columns={"total_runs": "target_final_score"})
    )
    df = df.merge(innings_totals, on=["match_id", "inning"], how="left")

    # Add winner context if available.
    if {"id", "winner"}.issubset(matches_df.columns):
        winner_frame = matches_df[["id", "winner"]].rename(columns={"id": "match_id", "winner": "match_winner"})
        df = df.merge(winner_frame, on="match_id", how="left")

    return df


def build_winner_training_dataset(matches_df: pd.DataFrame) -> pd.DataFrame:
    """Build pre-match winner training dataset."""
    return build_prematch_features(matches_df)


def build_score_training_dataset(ball_features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build live score training dataset from ball-level snapshots.

    Model target: `target_final_score`.
    """
    df = ball_features_df.copy()
    if "target_final_score" not in df.columns:
        raise ValueError("ball_features_df missing target_final_score")

    df["batting_team_id"] = pd.Categorical(df["batting_team"]).codes
    df["bowling_team_id"] = pd.Categorical(df["bowling_team"]).codes

    feature_cols = [
        "match_id",
        "inning",
        "batting_team_id",
        "bowling_team_id",
        "runs",
        "wickets",
        "overs",
        "balls_left",
        "current_run_rate",
        "required_run_rate",
        "target",
        "target_final_score",
    ]
    available_cols = [col for col in feature_cols if col in df.columns]
    out = df[available_cols].copy()
    if "target" in out.columns:
        out["target"] = out["target"].fillna(0.0)
    else:
        out["target"] = 0.0
    return out


def build_live_features(match_state: Dict[str, float]) -> pd.DataFrame:
    """
    Convert live match state dict into a model-ready dataframe.

    Expected keys can include:
    current_runs, wickets, overs, target, required_rr, current_rr, etc.
    """
    runs = float(match_state.get("runs", match_state.get("current_runs", 0.0)))
    wickets = float(match_state.get("wickets", 0.0))
    overs = float(match_state.get("overs", 0.0))
    target = float(match_state.get("target", 0.0)) if match_state.get("target") is not None else 0.0

    # Handles cricket-style over notation (e.g., 9.4 means 9 overs + 4 balls).
    whole_overs = int(overs)
    partial_balls = int(round((overs - whole_overs) * 10))
    balls_bowled = max((whole_overs * 6) + partial_balls, 0)
    balls_left = max(120 - balls_bowled, 0)
    current_run_rate = (runs / overs) if overs > 0 else 0.0
    runs_remaining = max(target - runs, 0.0)
    required_run_rate = (runs_remaining * 6.0 / balls_left) if balls_left > 0 else 0.0

    payload = {
        "runs": runs,
        "wickets": wickets,
        "overs": overs,
        "balls_left": float(balls_left),
        "current_run_rate": current_run_rate,
        "required_run_rate": required_run_rate,
        "target": target,
    }
    return pd.DataFrame([payload])
