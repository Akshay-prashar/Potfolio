"""Optional safe retraining script for winner and score models."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from backend.app.services.prediction_service import PredictionService
from backend.app.utils.features import build_prematch_features


def _load_csv_if_exists(path: Path) -> Optional[pd.DataFrame]:
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return None


def retrain_models(
    training_data_path: Path | str = "data/training_data.csv",
    simulation_results_path: Path | str = "data/processed/simulation_results.csv",
    winner_training_path: Path | str = "data/processed/winner_training.csv",
) -> None:
    """
    Retrain models using available datasets.

    Safe behavior:
    - Retrains only when required datasets are present.
    - Skips missing components gracefully.
    """
    model_service = PredictionService()

    # Winner model retrain.
    winner_df = _load_csv_if_exists(Path(winner_training_path))
    if winner_df is not None and "team1_won" in winner_df.columns:
        winner_features = build_prematch_features(winner_df) if "team1" in winner_df.columns else winner_df
        model_service.train_winner_model(winner_features, target_col="team1_won")
        print("Winner model retrained.")
    else:
        print("Winner model retrain skipped (winner training data unavailable).")

    # Score model retrain: use training_data + append simulation checkpoints as extra rows.
    training_df = _load_csv_if_exists(Path(training_data_path))
    sim_df = _load_csv_if_exists(Path(simulation_results_path))
    if training_df is None:
        print("Score model retrain skipped (training_data.csv unavailable).")
        return

    # Build score target from per-ball data: final innings score.
    score_base = training_df.copy()
    score_base["match_id"] = pd.to_numeric(score_base["match_id"], errors="coerce")
    score_base["inning"] = pd.to_numeric(score_base["inning"], errors="coerce")
    score_base["runs"] = pd.to_numeric(score_base["runs"], errors="coerce").fillna(0)
    score_base["wickets"] = pd.to_numeric(score_base["wickets"], errors="coerce").fillna(0)
    score_base["over"] = pd.to_numeric(score_base["over"], errors="coerce").fillna(0)
    score_base["ball"] = pd.to_numeric(score_base["ball"], errors="coerce").fillna(0)

    score_base["balls_bowled"] = (score_base["over"].astype(int) * 6 + score_base["ball"].astype(int)).clip(lower=0)
    score_base["overs"] = score_base["balls_bowled"].apply(lambda b: round((b // 6) + (b % 6) / 10, 1))
    score_base["balls_left"] = (120 - score_base["balls_bowled"]).clip(lower=0)

    score_base = score_base.sort_values(["match_id", "inning", "over", "ball"]).reset_index(drop=True)
    score_base["runs_so_far"] = score_base.groupby(["match_id", "inning"])["runs"].cumsum()
    score_base["current_run_rate"] = score_base.apply(
        lambda r: (r["runs_so_far"] * 6 / r["balls_bowled"]) if r["balls_bowled"] > 0 else 0.0,
        axis=1,
    )
    final_scores = (
        score_base.groupby(["match_id", "inning"], as_index=False)["runs"]
        .sum()
        .rename(columns={"runs": "target_final_score"})
    )
    score_base = score_base.merge(final_scores, on=["match_id", "inning"], how="left")

    score_dataset = pd.DataFrame(
        {
            "match_id": score_base["match_id"],
            "inning": score_base["inning"],
            "batting_team_id": pd.Categorical(score_base["batting_team"]).codes,
            "bowling_team_id": pd.Categorical(score_base["bowling_team"]).codes,
            "runs": score_base["runs_so_far"],
            "wickets": score_base["wickets"],
            "overs": score_base["overs"],
            "balls_left": score_base["balls_left"],
            "current_run_rate": score_base["current_run_rate"],
            "required_run_rate": 0.0,
            "target": 0.0,
            "target_final_score": score_base["target_final_score"],
        }
    )

    if sim_df is not None and {"runs", "wickets", "overs", "actual_score"}.issubset(sim_df.columns):
        sim_aug = pd.DataFrame(
            {
                "match_id": pd.to_numeric(sim_df.get("match_id"), errors="coerce"),
                "inning": pd.to_numeric(sim_df.get("inning"), errors="coerce"),
                "batting_team_id": pd.Categorical(sim_df.get("batting_team")).codes,
                "bowling_team_id": pd.Categorical(sim_df.get("bowling_team")).codes,
                "runs": pd.to_numeric(sim_df.get("runs"), errors="coerce"),
                "wickets": pd.to_numeric(sim_df.get("wickets"), errors="coerce"),
                "overs": pd.to_numeric(sim_df.get("overs"), errors="coerce"),
                "balls_left": 0.0,
                "current_run_rate": 0.0,
                "required_run_rate": 0.0,
                "target": 0.0,
                "target_final_score": pd.to_numeric(sim_df.get("actual_score"), errors="coerce"),
            }
        ).dropna()
        score_dataset = pd.concat([score_dataset, sim_aug], ignore_index=True)

    score_dataset = score_dataset.dropna()
    model_service.train_score_model(score_dataset, target_col="target_final_score")
    print("Score model retrained.")


if __name__ == "__main__":
    retrain_models()

