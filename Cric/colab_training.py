"""Google Colab-ready IPL training script using XGBoost.

This script:
1. Installs required libraries
2. Loads /content/matches.csv and /content/deliveries.csv
3. Cleans/merges data
4. Builds live features
5. Encodes categorical variables
6. Trains winner classifier + score regressor
7. Evaluates (Accuracy, RMSE)
8. Saves models and triggers download in Colab
"""

import subprocess
import sys


def install_libraries() -> None:
    """Install runtime dependencies in Colab."""
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "xgboost", "pandas", "scikit-learn", "joblib"]
    )


install_libraries()

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import accuracy_score, mean_squared_error  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.preprocessing import LabelEncoder  # noqa: E402
from xgboost import XGBClassifier, XGBRegressor  # noqa: E402


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names for robust processing."""
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def main() -> None:
    # 2) Load datasets
    matches_path = "/content/matches.csv"
    deliveries_path = "/content/deliveries.csv"

    matches = pd.read_csv(matches_path, low_memory=False)
    deliveries = pd.read_csv(deliveries_path, low_memory=False)

    matches = normalize_columns(matches)
    deliveries = normalize_columns(deliveries)

    # 3) Data cleaning (matches): keep required columns and drop nulls
    required_match_cols = ["id", "team1", "team2", "winner"]
    if "match_id" in matches.columns and "id" not in matches.columns:
        matches = matches.rename(columns={"match_id": "id"})
    missing_match_cols = [c for c in required_match_cols if c not in matches.columns]
    if missing_match_cols:
        raise ValueError(f"matches.csv missing required columns: {missing_match_cols}")
    matches = matches[required_match_cols].dropna().copy()

    # Prepare deliveries schema
    if "id" in deliveries.columns and "match_id" not in deliveries.columns:
        deliveries = deliveries.rename(columns={"id": "match_id"})
    if "inning" not in deliveries.columns and "innings" in deliveries.columns:
        deliveries = deliveries.rename(columns={"innings": "inning"})
    if "total_runs" not in deliveries.columns:
        raise ValueError("deliveries.csv must contain 'total_runs'")
    for c in ["match_id", "inning", "batting_team", "bowling_team", "over", "ball", "total_runs"]:
        if c not in deliveries.columns:
            raise ValueError(f"deliveries.csv missing required column: {c}")

    deliveries = deliveries.copy()
    deliveries["match_id"] = pd.to_numeric(deliveries["match_id"], errors="coerce")
    deliveries["inning"] = pd.to_numeric(deliveries["inning"], errors="coerce")
    deliveries["over"] = pd.to_numeric(deliveries["over"], errors="coerce")
    deliveries["ball"] = pd.to_numeric(deliveries["ball"], errors="coerce")
    deliveries["total_runs"] = pd.to_numeric(deliveries["total_runs"], errors="coerce").fillna(0)

    deliveries = deliveries.dropna(
        subset=["match_id", "inning", "batting_team", "bowling_team", "over", "ball"]
    ).copy()
    deliveries["match_id"] = deliveries["match_id"].astype(int)
    deliveries["inning"] = deliveries["inning"].astype(int)

    # 4) Merge deliveries with matches using match_id
    merged = deliveries.merge(
        matches.rename(columns={"id": "match_id"}),
        on="match_id",
        how="inner",
    )

    # Ensure clean text
    for c in ["batting_team", "bowling_team", "winner"]:
        merged[c] = merged[c].astype(str).str.strip()

    # Sort for cumulative features
    merged = merged.sort_values(["match_id", "inning", "over", "ball"]).reset_index(drop=True)

    # 5) Feature Engineering
    merged["runs"] = merged.groupby(["match_id", "inning"])["total_runs"].cumsum()

    if "is_wicket" in merged.columns:
        wicket_fell = pd.to_numeric(merged["is_wicket"], errors="coerce").fillna(0).clip(lower=0, upper=1)
    elif "player_dismissed" in merged.columns:
        wicket_fell = merged["player_dismissed"].fillna("").astype(str).str.strip().ne("").astype(int)
    else:
        wicket_fell = pd.Series(0, index=merged.index)

    merged["wickets"] = wicket_fell.groupby([merged["match_id"], merged["inning"]]).cumsum()

    # Requested formula: overs = over + ball/10
    merged["overs"] = merged["over"] + (merged["ball"] / 10.0)

    # Count rows as balls bowled snapshot index
    merged["balls_bowled"] = merged.groupby(["match_id", "inning"]).cumcount() + 1
    merged["balls_left"] = (120 - merged["balls_bowled"]).clip(lower=0)
    merged["current_run_rate"] = (merged["runs"] * 6.0) / merged["balls_bowled"].replace(0, np.nan)
    merged["current_run_rate"] = merged["current_run_rate"].fillna(0.0)

    # Build final innings score target for regression
    final_scores = (
        merged.groupby(["match_id", "inning"], as_index=False)["total_runs"]
        .sum()
        .rename(columns={"total_runs": "final_score"})
    )
    merged = merged.merge(final_scores, on=["match_id", "inning"], how="left")

    # 6) Encode categorical variables
    batting_encoder = LabelEncoder()
    bowling_encoder = LabelEncoder()
    winner_encoder = LabelEncoder()

    merged["batting_team_enc"] = batting_encoder.fit_transform(merged["batting_team"])
    merged["bowling_team_enc"] = bowling_encoder.fit_transform(merged["bowling_team"])
    merged["winner_enc"] = winner_encoder.fit_transform(merged["winner"])

    feature_cols = [
        "batting_team_enc",
        "bowling_team_enc",
        "runs",
        "wickets",
        "overs",
        "balls_left",
        "current_run_rate",
    ]

    # 7) Train Model 1: winner classifier
    x_cls = merged[feature_cols]
    y_cls = merged["winner_enc"]

    x_cls_train, x_cls_test, y_cls_train, y_cls_test = train_test_split(
        x_cls,
        y_cls,
        test_size=0.2,
        random_state=42,
        stratify=y_cls,
    )

    n_classes = int(y_cls.nunique())
    winner_model = XGBClassifier(
        n_estimators=250,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="multi:softprob",
        num_class=n_classes,
        eval_metric="mlogloss",
        tree_method="hist",  # CPU-friendly
        n_jobs=-1,
        random_state=42,
    )
    winner_model.fit(x_cls_train, y_cls_train)

    # 8) Train Model 2: score regressor
    x_reg = merged[feature_cols]
    y_reg = merged["final_score"]

    x_reg_train, x_reg_test, y_reg_train, y_reg_test = train_test_split(
        x_reg,
        y_reg,
        test_size=0.2,
        random_state=42,
    )

    score_model = XGBRegressor(
        n_estimators=350,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        tree_method="hist",  # CPU-friendly
        n_jobs=-1,
        random_state=42,
    )
    score_model.fit(x_reg_train, y_reg_train)

    # 9) Evaluation
    cls_pred = winner_model.predict(x_cls_test)
    accuracy = accuracy_score(y_cls_test, cls_pred)

    reg_pred = score_model.predict(x_reg_test)
    mse = mean_squared_error(y_reg_test, reg_pred)
    rmse = float(np.sqrt(mse))

    print(f"Classification Accuracy: {accuracy:.4f}")
    print(f"Regression RMSE: {rmse:.4f}")

    # 10) Save models
    joblib.dump(winner_model, "/content/winner_model.pkl")
    joblib.dump(score_model, "/content/score_model.pkl")

    # Optional: save encoders for inference consistency
    joblib.dump(
        {
            "batting_encoder_classes": batting_encoder.classes_.tolist(),
            "bowling_encoder_classes": bowling_encoder.classes_.tolist(),
            "winner_encoder_classes": winner_encoder.classes_.tolist(),
            "feature_cols": feature_cols,
        },
        "/content/preprocessing_objects.pkl",
    )

    print("Saved: /content/winner_model.pkl")
    print("Saved: /content/score_model.pkl")
    print("Saved: /content/preprocessing_objects.pkl")

    # 11) Download models in Colab
    try:
        from google.colab import files  # type: ignore

        files.download("/content/winner_model.pkl")
        files.download("/content/score_model.pkl")
    except Exception as exc:
        print(f"Colab download skipped: {exc}")


if __name__ == "__main__":
    main()
