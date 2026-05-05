"""Live match service that combines scraping and prediction logic."""

from typing import Any, Dict

from .prediction_service import PredictionService
from .scrape_service import ScrapeService


class LiveService:
    """Coordinates live data fetch and inference."""

    def __init__(
        self,
        scrape_service: ScrapeService | None = None,
        prediction_service: PredictionService | None = None,
    ) -> None:
        self.scrape_service = scrape_service or ScrapeService()
        self.prediction_service = prediction_service or PredictionService()

    def get_live_match_data(self, match_id: str) -> Dict[str, Any]:
        """Fetch raw live data for a match."""
        return self.scrape_service.scrape_live_match_data(match_id)

    def live_prediction(self, match_state: Dict[str, float]) -> Dict[str, float]:
        """Run live model prediction based on current match state."""
        return self.prediction_service.predict_live_outcome(match_state)

