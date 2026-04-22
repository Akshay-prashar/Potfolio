"""Pydantic schemas for request and response payloads."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PrematchPredictionRequest(BaseModel):
    """Input payload for pre-match winner prediction."""

    team1: str = Field(..., description="First team name")
    team2: str = Field(..., description="Second team name")
    venue: Optional[str] = Field(default=None, description="Match venue")
    toss_winner: Optional[str] = Field(default=None, description="Toss winner")
    toss_decision: Optional[str] = Field(
        default=None, description="Toss decision (bat/field)"
    )


class LivePredictionRequest(BaseModel):
    """Input payload for live prediction after match starts."""

    match_id: str = Field(..., description="Unique match identifier")
    batting_team: str
    bowling_team: str
    current_runs: int
    wickets: int
    overs: float
    target: Optional[int] = Field(default=None, description="Target runs in chase")


class PredictionResponse(BaseModel):
    """Unified prediction response payload."""

    model_name: str
    prediction: Any
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LiveMatchResponse(BaseModel):
    """Live match score payload from scrape/API source."""

    match_id: str
    source: str
    raw_data: Dict[str, Any]

