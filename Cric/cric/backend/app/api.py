"""FastAPI route handlers for model training and prediction APIs."""

from fastapi import APIRouter, HTTPException

from .schemas import (
    LiveMatchResponse,
    LivePredictionRequest,
    PredictionResponse,
    PrematchPredictionRequest,
)
from .services.live_service import LiveService
from .services.prediction_service import PredictionService

router = APIRouter()
prediction_service = PredictionService()
live_service = LiveService(prediction_service=prediction_service)


@router.get("/health")
def health_check() -> dict[str, str]:
    """Health endpoint to verify API status."""
    return {"status": "ok"}


@router.post("/predict/prematch", response_model=PredictionResponse)
def predict_prematch(payload: PrematchPredictionRequest) -> PredictionResponse:
    """Predict winner before toss/match progression (placeholder)."""
    try:
        result = prediction_service.predict_prematch_winner(payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    confidence = float(max(result["probabilities"]))
    return PredictionResponse(
        model_name="winner_model",
        prediction=result["prediction"],
        confidence=confidence,
        metadata={"probabilities": result["probabilities"]},
    )


@router.post("/predict/live", response_model=PredictionResponse)
def predict_live(payload: LivePredictionRequest) -> PredictionResponse:
    """Predict live outcome based on current score state."""
    try:
        result = live_service.live_prediction(payload.model_dump(exclude={"match_id"}))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PredictionResponse(
        model_name="score_model",
        prediction=result["predicted_final_score"],
        confidence=None,
        metadata={"match_id": payload.match_id},
    )


@router.get("/live/match/{match_id}", response_model=LiveMatchResponse)
def get_live_match(match_id: str) -> LiveMatchResponse:
    """Fetch live score data using scraper/API integration placeholder."""
    data = live_service.get_live_match_data(match_id)
    return LiveMatchResponse(match_id=match_id, source=data.get("source", "unknown"), raw_data=data)

