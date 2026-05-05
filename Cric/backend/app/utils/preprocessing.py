"""Dataset loading, cleaning, and normalization utilities."""

from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from .helpers import clean_column_names, ensure_columns, to_numeric


TEAM_NAME_MAP: Dict[str, str] = {
    "delhi_daredevils": "delhi_capitals",
    "deccan_chargers": "sunrisers_hyderabad",
    "kings_xi_punjab": "punjab_kings",
    "rising_pune_supergiants": "rising_pune_supergiant",
    "pune_warriors": "pune_warriors_india",
}


def _normalize_team_name(name: object) -> str:
    """Normalize a raw team name into a canonical token."""
    if pd.isna(name):
        return "unknown_team"
    normalized = str(name).strip().lower().replace("&", "and").replace(" ", "_")
    return TEAM_NAME_MAP.get(normalized, normalized)


def _fill_text_columns(df: pd.DataFrame, default_value: str = "unknown") -> pd.DataFrame:
    """Fill all object/string columns with a default placeholder."""
    out = df.copy()
    text_cols = out.select_dtypes(include=["object"]).columns.tolist()
    for col in text_cols:
        out[col] = out[col].fillna(default_value)
    return out


def load_datasets(
    matches_path: Path,
    deliveries_path: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load IPL matches and deliveries datasets.

    CSV files are expected at:
    - data/raw/matches.csv
    - data/raw/deliveries.csv
    """
    if not matches_path.exists():
        raise FileNotFoundError(f"Missing matches dataset at {matches_path}")
    if not deliveries_path.exists():
        raise FileNotFoundError(f"Missing deliveries dataset at {deliveries_path}")

    matches_df = pd.read_csv(matches_path, low_memory=False)
    deliveries_df = pd.read_csv(deliveries_path, low_memory=False)
    return matches_df, deliveries_df


def preprocess_matches(matches_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean matches dataset and normalize team naming.

    Output schema is robust to common IPL dataset variants.
    """
    df = clean_column_names(matches_df)

    # Harmonize match identifier column name.
    if "match_id" in df.columns and "id" not in df.columns:
        df = df.rename(columns={"match_id": "id"})
    ensure_columns(df, required_columns=["id", "team1", "team2"], df_name="matches")

    # Normalize canonical text fields if present.
    team_columns = ["team1", "team2", "toss_winner", "winner"]
    for col in team_columns:
        if col in df.columns:
            df[col] = df[col].map(_normalize_team_name)

    if "toss_decision" in df.columns:
        df["toss_decision"] = (
            df["toss_decision"].astype(str).str.strip().str.lower().fillna("unknown")
        )

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["season"] = pd.to_numeric(df.get("season"), errors="coerce")
        df["season"] = df["season"].fillna(df["date"].dt.year)

    numeric_cols = ["id", "season", "dl_applied", "win_by_runs", "win_by_wickets"]
    df = to_numeric(df, numeric_cols, fill_value=0.0)
    df = _fill_text_columns(df, default_value="unknown")
    return df


def preprocess_deliveries(deliveries_df: pd.DataFrame) -> pd.DataFrame:
    """Clean deliveries data with robust numeric and text handling."""
    df = clean_column_names(deliveries_df)

    # Harmonize match identifier column name.
    if "id" in df.columns and "match_id" not in df.columns:
        df = df.rename(columns={"id": "match_id"})
    ensure_columns(
        df,
        required_columns=["match_id", "inning", "batting_team", "bowling_team", "total_runs"],
        df_name="deliveries",
    )

    team_columns = ["batting_team", "bowling_team"]
    for col in team_columns:
        if col in df.columns:
            df[col] = df[col].map(_normalize_team_name)

    numeric_cols = [
        "match_id",
        "inning",
        "over",
        "ball",
        "total_runs",
        "wide_runs",
        "noball_runs",
        "batsman_runs",
        "extra_runs",
        "is_wicket",
    ]
    df = to_numeric(df, numeric_cols, fill_value=0.0)

    # Dismissal columns are needed for wicket tracking.
    if "player_dismissed" not in df.columns:
        df["player_dismissed"] = ""
    if "dismissal_kind" not in df.columns:
        df["dismissal_kind"] = "none"

    df["player_dismissed"] = df["player_dismissed"].fillna("").astype(str).str.strip()
    df["dismissal_kind"] = df["dismissal_kind"].fillna("none").astype(str).str.strip().str.lower()

    df = _fill_text_columns(df, default_value="unknown")
    return df


def get_team_id_mapping(matches_df: pd.DataFrame, deliveries_df: pd.DataFrame) -> Dict[str, int]:
    """Create deterministic team-to-integer mapping for model-ready features."""
    teams = set()
    for col in ["team1", "team2", "toss_winner", "winner"]:
        if col in matches_df.columns:
            teams.update(matches_df[col].dropna().astype(str).tolist())
    for col in ["batting_team", "bowling_team"]:
        if col in deliveries_df.columns:
            teams.update(deliveries_df[col].dropna().astype(str).tolist())

    teams = sorted(team for team in teams if team)
    return {team: idx for idx, team in enumerate(teams)}
