"""Run complete IPL preprocessing and feature engineering pipeline."""

from pathlib import Path

from backend.app.utils.features import (
    build_ball_by_ball_features,
    build_score_training_dataset,
    build_winner_training_dataset,
)
from backend.app.utils.helpers import ensure_dir, save_csv
from backend.app.utils.preprocessing import (
    load_datasets,
    preprocess_deliveries,
    preprocess_matches,
)


def run_preprocessing() -> None:
    """
    Execute end-to-end data pipeline.

    Inputs:
    - data/raw/matches.csv
    - data/raw/deliveries.csv

    Outputs in data/processed:
    - matches_clean.csv
    - deliveries_clean.csv
    - ball_by_ball_features.csv
    - live_features.csv
    - winner_training.csv
    - score_training.csv
    """
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    ensure_dir(processed_dir)

    matches_path = raw_dir / "matches.csv"
    deliveries_path = raw_dir / "deliveries.csv"

    matches_raw, deliveries_raw = load_datasets(matches_path, deliveries_path)

    # Step 1-3: clean missing values and normalize team names.
    matches_clean = preprocess_matches(matches_raw)
    deliveries_clean = preprocess_deliveries(deliveries_raw)

    # Step 4-5: build match-level and ball-by-ball + live-state features.
    ball_features = build_ball_by_ball_features(deliveries_clean, matches_clean)
    live_feature_cols = [
        "match_id",
        "inning",
        "batting_team",
        "bowling_team",
        "runs",
        "wickets",
        "overs",
        "balls_left",
        "current_run_rate",
        "required_run_rate",
        "target",
        "target_final_score",
    ]
    available_live_cols = [col for col in live_feature_cols if col in ball_features.columns]
    live_features = ball_features[available_live_cols].copy()

    # Step 7: prepare model training datasets.
    winner_training = build_winner_training_dataset(matches_clean)
    score_training = build_score_training_dataset(ball_features)

    # Step 6: save all artifacts to data/processed.
    save_csv(matches_clean, processed_dir / "matches_clean.csv")
    save_csv(deliveries_clean, processed_dir / "deliveries_clean.csv")
    save_csv(ball_features, processed_dir / "ball_by_ball_features.csv")
    save_csv(live_features, processed_dir / "live_features.csv")
    save_csv(winner_training, processed_dir / "winner_training.csv")
    save_csv(score_training, processed_dir / "score_training.csv")

    print("Preprocessing pipeline complete.")
    print(f"Processed files saved to: {processed_dir.resolve()}")


if __name__ == "__main__":
    run_preprocessing()
