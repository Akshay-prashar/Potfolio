"""Model training and inference logic for IPL predictions."""

from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from ..config import MODELS_DIR, SCORE_MODEL_PATH, WINNER_MODEL_PATH
from ..utils.features import build_live_features, build_prematch_features
from ..utils.helpers import ensure_dir, load_joblib, save_joblib


class PredictionService:
    """Owns model lifecycle for winner and score prediction models."""

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.models_dir = models_dir
        ensure_dir(self.models_dir)

    def train_winner_model(self, feature_df: pd.DataFrame, target_col: str) -> XGBClassifier:
        """Train pre-match winner classifier (placeholder baseline)."""
        if target_col not in feature_df.columns:
            raise ValueError(f"Target column '{target_col}' not found.")

        x = feature_df.drop(columns=[target_col])
        y = feature_df[target_col]

        model = XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            tree_method="hist",  # CPU-friendly
            n_jobs=-1,
            random_state=42,
        )
        model.fit(x, y)
        save_joblib(model, WINNER_MODEL_PATH)
        return model

    def train_score_model(self, feature_df: pd.DataFrame, target_col: str) -> XGBRegressor:
        """Train live score regressor (placeholder baseline)."""
        if target_col not in feature_df.columns:
            raise ValueError(f"Target column '{target_col}' not found.")

        x = feature_df.drop(columns=[target_col])
        y = feature_df[target_col]

        model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="reg:squarederror",
            tree_method="hist",  # CPU-friendly
            n_jobs=-1,
            random_state=42,
        )
        model.fit(x, y)
        save_joblib(model, SCORE_MODEL_PATH)
        return model

    def load_models(self) -> Tuple[XGBClassifier, XGBRegressor]:
        """Load winner and score models from disk."""
        winner_model = load_joblib(WINNER_MODEL_PATH)
        score_model = load_joblib(SCORE_MODEL_PATH)
        return winner_model, score_model

    def predict_prematch_winner(self, payload: Dict[str, object]) -> Dict[str, object]:
        """Generate pre-match winner probability using saved classifier."""
        winner_model = load_joblib(WINNER_MODEL_PATH)
        features = build_prematch_features(pd.DataFrame([payload]))
        probabilities = winner_model.predict_proba(features)[0].tolist()
        prediction = int(probabilities[1] >= 0.5)
        return {"prediction": prediction, "probabilities": probabilities}

    def predict_live_outcome(self, match_state: Dict[str, float]) -> Dict[str, float]:
        """Generate live score/win proxy prediction from running match state."""
        score_model = load_joblib(SCORE_MODEL_PATH)
        features = build_live_features(match_state)
        predicted_score = float(score_model.predict(features)[0])
        return {"predicted_final_score": predicted_score}

