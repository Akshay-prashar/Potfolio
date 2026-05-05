"""Download data placeholder script.

In production, connect this script to a reliable IPL data source.
"""

from pathlib import Path

from backend.app.utils.helpers import ensure_dir


def download_datasets() -> None:
    """Create raw data directory and print expected file locations."""
    raw_dir = Path("data/raw")
    ensure_dir(raw_dir)
    print("Place datasets at:")
    print(f"- {raw_dir / 'matches.csv'}")
    print(f"- {raw_dir / 'deliveries.csv'}")


if __name__ == "__main__":
    download_datasets()

