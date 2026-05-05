"""Quick scraper verification script."""

from __future__ import annotations

import json
import sys

from scraper import CricinfoScrapeError, scrape_live_match


def main() -> None:
    """
    Test scraper output format.

    Usage:
    - Auto live mode: python test_scraper.py
    - URL mode:       python test_scraper.py "<espn_cricinfo_url>"
    """
    url = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        data = scrape_live_match(url=url, timeout=15)
        print(json.dumps(data, indent=2))
    except CricinfoScrapeError as exc:
        print(f"Scraper error: {exc}")
        raise SystemExit(2)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Unexpected error: {exc}")
        raise SystemExit(3)


if __name__ == "__main__":
    main()

