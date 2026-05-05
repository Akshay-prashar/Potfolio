"""Train pre-match winner model (XGBoostClassifier) from processed dataset."""

import argparse
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


def _encode_features(
    df: pd.DataFrame,
    target_col: str,
) -> Tuple[pd.DataFrame, pd.Series, Dict[str, Dict[str, int]]]:
    """Encode categorical columns to numeric ids and return X, y, encoder maps."""
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
    y = y.loc[valid_mask].astype(int).reset_index(drop=True)
    return x, y, encoder_maps


def train_winner_model(
    input_path: Path,
    model_path: Path,
    preprocessor_path: Path,
    target_col: str,
    test_size: float,
    random_state: int,
) -> None:
    """Train, evaluate, and save winner classifier + preprocessing metadata."""
    if not input_path.exists():
        raise FileNotFoundError(
            f"Processed dataset not found at {input_path}. Run scripts/preprocess_data.py first."
        )

    df = pd.read_csv(input_path, low_memory=False)
    x, y, encoder_maps = _encode_features(df=df, target_col=target_col)

    if y.nunique() < 2:
        raise ValueError("Winner target must contain at least two classes.")

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",  # CPU-friendly
        n_jobs=-1,
        random_state=random_state,
    )
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    y_prob = model.predict_proba(x_test)[:, 1]

    print("Winner Model Evaluation")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred):.4f}")
    print(f"ROC-AUC: {roc_auc_score(y_test, y_prob):.4f}")
    print("Classification Report:")
    print(classification_report(y_test, y_pred, digits=4))

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
    print(f"Saved winner model to: {model_path}")
    print(f"Saved winner preprocessing metadata to: {preprocessor_path}")


def _parse_args() -> argparse.Namespace:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Train IPL winner prediction model.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/winner_training.csv"),
        help="Path to winner training dataset.",
    )
    parser.add_argument(
        "--target-col",
        type=str,
        default="team1_won",
        help="Target column for winner classification.",
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
        default=Path("models/winner_model.joblib"),
        help="Output path for trained model artifact.",
    )
    parser.add_argument(
        "--preprocessor-path",
        type=Path,
        default=Path("models/winner_preprocessor.joblib"),
        help="Output path for preprocessing metadata artifact.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train_winner_model(
        input_path=args.input,
        model_path=args.model_path,
        preprocessor_path=args.preprocessor_path,
        target_col=args.target_col,
        test_size=args.test_size,
        random_state=args.random_state,
    )
