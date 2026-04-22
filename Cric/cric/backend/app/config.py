"""Application configuration module."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"

MATCHES_CSV_PATH = DATA_RAW_DIR / "matches.csv"
DELIVERIES_CSV_PATH = DATA_RAW_DIR / "deliveries.csv"

WINNER_MODEL_PATH = MODELS_DIR / "winner_model.joblib"
SCORE_MODEL_PATH = MODELS_DIR / "score_model.joblib"

