"""Build unified training dataset with session checkpoint scores."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from inference import SESSION_CHECKPOINTS


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def _first_existing(df: pd.DataFrame, candidates: List[str], default: str = "") -> pd.Series:
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([default] * len(df))


def _compute_checkpoint_scores(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Compute actual cumulative scores at each session checkpoint for every innings.

    Returns a DataFrame with columns:
        match_id, inning, target_over, checkpoint_actual_score
    """
    records = []
    for (match_id, inning), innings_df in deliveries.groupby(["match_id", "inning"]):
        # Compute ball position and cumulative runs.
        idf = innings_df.sort_values(["over", "ball"]).reset_index(drop=True)
        idf["ball_pos"] = idf.apply(
            lambda r: max(int(r["over"]) * 6 + int(r["ball"]), 0), axis=1
        )
        idf["cum_runs"] = pd.to_numeric(idf["total_runs"], errors="coerce").fillna(0).cumsum()

        final_score = int(idf["cum_runs"].iloc[-1]) if len(idf) > 0 else 0

        for target_over in SESSION_CHECKPOINTS:
            target_balls = target_over * 6
            rows_at = idf[idf["ball_pos"] <= target_balls]
            if rows_at.empty:
                score = 0
            else:
                score = int(rows_at["cum_runs"].iloc[-1])

            # For 20 overs, use final score.
            if target_over == 20:
                score = final_score

            records.append({
                "match_id": int(match_id),
                "inning": int(inning),
                "target_over": target_over,
                "checkpoint_actual_score": score,
            })

    return pd.DataFrame(records)


def build_training_data(
    matches_path: Path | str = "data/raw/matches1.csv",
    deliveries_path: Path | str = "data/raw/deliveries.csv",
    output_path: Path | str = "data/training_data.csv",
) -> Path:
    """Create per-ball CSV with match + contextual fields + checkpoint scores.

    Output columns include:
    - match_id, inning, over, ball, runs, wickets, batting_team, bowling_team,
      batsman, bowler, stadium, city, weather, winner
    - target_over, checkpoint_actual_score (for each session checkpoint)
    """
    matches_file = Path(matches_path)
    deliveries_file = Path(deliveries_path)
    output_file = Path(output_path)

    if not matches_file.exists():
        raise FileNotFoundError(f"Missing matches file: {matches_file}")
    if not deliveries_file.exists():
        raise FileNotFoundError(f"Missing deliveries file: {deliveries_file}")

    matches = _normalize_columns(pd.read_csv(matches_file, low_memory=False))
    deliveries = _normalize_columns(pd.read_csv(deliveries_file, low_memory=False))

    if "id" in matches.columns and "match_id" not in matches.columns:
        matches = matches.rename(columns={"id": "match_id"})
    if "id" in deliveries.columns and "match_id" not in deliveries.columns:
        deliveries = deliveries.rename(columns={"id": "match_id"})
    if "innings" in deliveries.columns and "inning" not in deliveries.columns:
        deliveries = deliveries.rename(columns={"innings": "inning"})

    required_deliveries = ["match_id", "inning", "over", "ball", "batting_team", "bowling_team", "total_runs"]
    missing = [c for c in required_deliveries if c not in deliveries.columns]
    if missing:
        raise ValueError(f"deliveries.csv missing required columns: {missing}")

    # Derived per-ball fields.
    deliveries["runs"] = pd.to_numeric(deliveries["total_runs"], errors="coerce").fillna(0).astype(int)
    if "is_wicket" not in deliveries.columns:
        deliveries["is_wicket"] = 0
    deliveries["is_wicket"] = pd.to_numeric(deliveries["is_wicket"], errors="coerce").fillna(0).astype(int)
    deliveries = deliveries.sort_values(["match_id", "inning", "over", "ball"]).reset_index(drop=True)
    deliveries["wickets"] = deliveries.groupby(["match_id", "inning"])["is_wicket"].cumsum().clip(upper=10)

    deliveries["batsman"] = _first_existing(deliveries, ["batter", "batsman", "striker"], default="unknown")
    deliveries["bowler"] = _first_existing(deliveries, ["bowler"], default="unknown")

    match_meta = pd.DataFrame(
        {
            "match_id": matches["match_id"] if "match_id" in matches.columns else pd.Series([], dtype="int64"),
            "stadium": _first_existing(matches, ["venue", "stadium"], default="unknown_stadium"),
            "city": _first_existing(matches, ["city"], default="unknown_city"),
            "winner": _first_existing(matches, ["winner"], default="unknown"),
        }
    )

    merged = deliveries.merge(match_meta, on="match_id", how="left")
    merged["weather"] = "unknown"

    # Compute checkpoint scores.
    checkpoint_df = _compute_checkpoint_scores(deliveries)

    # Final required schema (per-ball rows).
    final = pd.DataFrame(
        {
            "match_id": pd.to_numeric(merged["match_id"], errors="coerce"),
            "inning": pd.to_numeric(merged["inning"], errors="coerce"),
            "over": pd.to_numeric(merged["over"], errors="coerce"),
            "ball": pd.to_numeric(merged["ball"], errors="coerce"),
            "runs": pd.to_numeric(merged["runs"], errors="coerce"),
            "wickets": pd.to_numeric(merged["wickets"], errors="coerce"),
            "batting_team": merged["batting_team"].astype(str),
            "bowling_team": merged["bowling_team"].astype(str),
            "batsman": merged["batsman"].astype(str),
            "bowler": merged["bowler"].astype(str),
            "stadium": merged["stadium"].fillna("unknown_stadium").astype(str),
            "city": merged["city"].fillna("unknown_city").astype(str),
            "weather": merged["weather"].astype(str),
            "winner": merged["winner"].fillna("unknown").astype(str),
        }
    )

    # Drop rows missing critical fields.
    final = final.dropna(subset=["match_id", "inning", "over", "ball", "runs", "wickets"])
    final = final[
        (final["batting_team"].str.strip() != "")
        & (final["bowling_team"].str.strip() != "")
    ]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_file, index=False)

    # Save checkpoint scores separately for retraining use.
    checkpoint_output = Path(output_path).parent / "checkpoint_scores.csv"
    checkpoint_df.to_csv(checkpoint_output, index=False)

    print(f"Saved training dataset: {output_file} ({len(final)} rows)")
    print(f"Saved checkpoint scores: {checkpoint_output} ({len(checkpoint_df)} rows)")
    return output_file


def export_simulation_snapshot(
    simulation_results_path: Path | str = "data/processed/simulation_results.csv",
    snapshot_path: Path | str = "data/processed/training_snapshot.csv",
) -> Path:
    """Export simulation results as a training snapshot for future retraining."""
    src = Path(simulation_results_path)
    dst = Path(snapshot_path)

    if not src.exists():
        raise FileNotFoundError(f"No simulation results at {src}. Run simulation first.")

    df = pd.read_csv(src, low_memory=False)
    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dst, index=False)
    print(f"Exported training snapshot: {dst} ({len(df)} rows)")
    return dst


if __name__ == "__main__":
    out = build_training_data()
    print(f"Saved training dataset to: {out}")
