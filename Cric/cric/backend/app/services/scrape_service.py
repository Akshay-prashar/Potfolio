"""Scraper/API client for live IPL match data."""

from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup


class ScrapeService:
    """Fetches and parses live score data from an external source."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or "https://example.com/live-score"

    def scrape_live_match_data(self, match_id: str) -> Dict[str, Any]:
        """
        Scrape live match details.

        Replace parsing logic with provider-specific selectors when integrating
        real score source or official API.
        """
        try:
            response = requests.get(
                f"{self.base_url}/{match_id}",
                timeout=10,
                headers={"User-Agent": "cric-predictor/0.1"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {"match_id": match_id, "error": str(exc), "source": self.base_url}

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.text.strip() if soup.title else "Live score page"
        return {
            "match_id": match_id,
            "source": self.base_url,
            "title": title,
            "raw_html_length": len(response.text),
        }

