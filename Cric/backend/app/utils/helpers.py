"""Generic helper utilities used across modules."""

from pathlib import Path
from typing import Any, Iterable

import joblib
import pandas as pd


def ensure_dir(path: Path) -> None:
    """Create a directory if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def save_joblib(obj: Any, path: Path) -> None:
    """Persist Python object to disk using joblib."""
    ensure_dir(path.parent)
    joblib.dump(obj, path)


def load_joblib(path: Path) -> Any:
    """Load joblib artifact if present."""
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    return joblib.load(path)


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize dataframe column names for predictable downstream code."""
    out = df.copy()
    out.columns = [str(col).strip().lower().replace(" ", "_") for col in out.columns]
    return out


def ensure_columns(df: pd.DataFrame, required_columns: Iterable[str], df_name: str) -> None:
    """Validate that a dataframe contains required columns."""
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{df_name} missing required columns: {missing}")


def to_numeric(df: pd.DataFrame, columns: Iterable[str], fill_value: float = 0.0) -> pd.DataFrame:
    """Safely coerce selected columns to numeric dtype."""
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(fill_value)
    return out


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Persist dataframe to CSV with parent directory creation."""
    ensure_dir(path.parent)
    df.to_csv(path, index=False)
