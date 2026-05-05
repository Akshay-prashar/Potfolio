"""Run a sample live prediction from command line."""

from backend.app.services.live_service import LiveService


def live_prediction() -> None:
    """Demo live prediction with placeholder match state."""
    service = LiveService()
    sample_state = {
        "current_runs": 78.0,
        "wickets": 2.0,
        "overs": 9.4,
        "target": 182.0,
    }
    result = service.live_prediction(sample_state)
    print("Live prediction result:", result)


if __name__ == "__main__":
    live_prediction()

