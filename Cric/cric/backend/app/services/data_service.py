"""Data service for loading and persisting processed datasets."""

from pathlib import Path
from typing import Tuple

import pandas as pd

from ..config import DATA_PROCESSED_DIR, DELIVERIES_CSV_PATH, MATCHES_CSV_PATH
from ..utils.helpers import ensure_dir
from ..utils.preprocessing import (
    load_datasets,
    preprocess_deliveries,
    preprocess_matches,
)


class DataService:
    """Provides dataset IO and preprocessing orchestration."""

    def __init__(self, processed_dir: Path = DATA_PROCESSED_DIR) -> None:
        self.processed_dir = processed_dir
        ensure_dir(self.processed_dir)

    def load_raw_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load raw CSV files from data/raw."""
        return load_datasets(MATCHES_CSV_PATH, DELIVERIES_CSV_PATH)

    def preprocess(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run cleaning pipeline for matches and deliveries datasets."""
        matches_df, deliveries_df = self.load_raw_data()
        return preprocess_matches(matches_df), preprocess_deliveries(deliveries_df)

    def save_processed(
        self,
        matches_df: pd.DataFrame,
        deliveries_df: pd.DataFrame,
    ) -> None:
        """Save processed datasets to data/processed."""
        matches_out = self.processed_dir / "matches_processed.csv"
        deliveries_out = self.processed_dir / "deliveries_processed.csv"
        matches_df.to_csv(matches_out, index=False)
        deliveries_df.to_csv(deliveries_out, index=False)

