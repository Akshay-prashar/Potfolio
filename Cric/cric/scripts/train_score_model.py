"""Train live score model (XGBoostRegressor) from processed dataset."""

import argparse
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor


def _encode_features(
    df: pd.DataFrame,
    target_col: str,
) -> Tuple[pd.DataFrame, pd.Series, Dict[str, Dict[str, int]]]:
    """Encode features into numeric matrix and return X, y, encoder mappings."""
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataframe.")

    data = df.copy()
    y = pd.to_numeric(data[target_col], errors="coerce")
    data = data.drop(columns=[target_col])

    encoder_maps: Dict[str, Dict[str, int]] = {}
    categorical_cols = data.select_dtypes(include=["object"]).columns.tolist()

    for col in categorical_cols:
        series = data[col].fillna("unknown").astype(str)
        categories = sorted(series.unique().tolist())
        mapping = {value: idx for idx, value in enumerate(categories)}
        encoder_maps[col] = mapping
        data[col] = series.map(mapping).astype(int)

    for col in data.columns:
        data[col] = pd.to_numeric(data[col], errors="coerce")
        median = data[col].median()
        data[col] = data[col].fillna(0.0 if np.isnan(median) else median)

    valid_mask = y.notna()
    x = data.loc[valid_mask].reset_index(drop=True)
    y = y.loc[valid_mask].astype(float).reset_index(drop=True)
    return x, y, encoder_maps


def train_score_model(
    input_path: Path,
    model_path: Path,
    preprocessor_path: Path,
    target_col: str,
    test_size: float,
    random_state: int,
) -> None:
    """Train, evaluate, and save score regressor + preprocessing metadata."""
    if not input_path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found at {input_path}. Run scripts/preprocess_data.py first."
        )

    df = pd.read_csv(input_path, low_memory=False)
    x, y, encoder_maps = _encode_features(df=df, target_col=target_col)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
    )

    model = XGBRegressor(
        n_estimators=400,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        tree_method="hist",  # CPU-friendly
        n_jobs=-1,
        random_state=random_state,
    )
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    rmse = mean_squared_error(y_test, y_pred, squared=False)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print("Score Model Evaluation")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE: {mae:.4f}")
    print(f"R2 Score: {r2:.4f}")

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    joblib.dump(
        {
            "target_col": target_col,
            "feature_cols": x.columns.tolist(),
            "categorical_encoders": encoder_maps,
        },
        preprocessor_path,
    )
    print(f"Saved score model to: {model_path}")
    print(f"Saved score preprocessing metadata to: {preprocessor_path}")


def _parse_args() -> argparse.Namespace:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Train IPL score prediction model.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/score_training.csv"),
        help="Path to score training dataset.",
    )
    parser.add_argument(
        "--target-col",
        type=str,
        default="target_final_score",
        help="Target column for score regression.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test split ratio (0-1).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path("models/score_model.joblib"),
        help="Output path for trained model artifact.",
    )
    parser.add_argument(
        "--preprocessor-path",
        type=Path,
        default=Path("models/score_preprocessor.joblib"),
        help="Output path for preprocessing metadata artifact.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train_score_model(
        input_path=args.input,
        model_path=args.model_path,
        preprocessor_path=args.preprocessor_path,
        target_col=args.target_col,
        test_size=args.test_size,
        random_state=args.random_state,
    )
