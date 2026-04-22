"""FastAPI backend for IPL session-based prediction system with rich match data."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from inference import predict_session, predict_live, SESSION_CHECKPOINTS
from scraper import CricinfoScrapeError, get_live_and_upcoming
from simulation_engine import run_simulation, get_available_matches
from accuracy_tracker import summarize_predictions, summarize_match


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ipl-api")
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"


# ── Schemas ───────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    batting_team: str = Field(..., min_length=1, max_length=100)
    bowling_team: str = Field(..., min_length=1, max_length=100)
    runs: float = Field(..., ge=0)
    wickets: float = Field(..., ge=0, le=10)
    overs: float = Field(..., ge=0)
    target_over: Optional[int] = None

    @field_validator("batting_team", "bowling_team")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Team name cannot be blank.")
        return v


class PredictResponse(BaseModel):
    batting_team: str
    bowling_team: str
    current_runs: int
    wickets: int
    overs: float
    target_over: int
    predicted_score: int
    predicted_winner: str
    win_percentage: str


class SimulateRequest(BaseModel):
    match_id: Optional[int] = None


class SessionPredictionRow(BaseModel):
    match_id: int
    inning: int
    batting_team: str
    bowling_team: str
    current_over: float
    target_over: int
    current_runs: int
    current_wickets: int
    predicted_score: Optional[int] = None
    actual_score: int
    error: Optional[float] = None
    result: Optional[str] = None
    predicted_winner: Optional[str] = None
    win_percentage: Optional[str] = None


class SimulationResponse(BaseModel):
    total_predictions: int
    correct: int
    wrong: int
    accuracy: float
    predictions: List[SessionPredictionRow]


class MatchInfo(BaseModel):
    match_id: int
    season: str
    team1: str
    team2: str
    winner: str
    venue: str
    label: str


# ── App ───────────────────────────────────────────────────────────────────

app = FastAPI(title="IPL Session Prediction API", version="3.0.0", docs_url="/docs")

cors_env = os.getenv("APP_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cors_env.strip() == "*" else [s.strip() for s in cors_env.split(",") if s.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def _val_err(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _generic_err(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/live")
def live_endpoint():
    """Rich live data: innings, batsmen, bowlers, playing XI, run rates, predictions."""
    try:
        data = get_live_and_upcoming()
    except Exception as exc:
        logger.warning("Scraper error: %s", exc)
        return {"status": "no_match", "live": None, "upcoming": []}

    upcoming = data.get("upcoming", [])
    detail = data.get("live_detail")
    basic = data.get("live_match_basic")

    if not detail and not basic:
        return {"status": "no_match", "live": None, "upcoming": upcoming}

    # Run prediction
    prediction = None
    if detail:
        runs = detail.get("runs", 0)
        wickets = detail.get("wickets", 0)
        overs = detail.get("overs", 0.0)
        batting = detail.get("batting_team", "Unknown")
        bowling = detail.get("bowling_team", "Unknown")
    elif basic:
        runs = basic.get("runs", 0)
        wickets = basic.get("wickets", 0)
        overs = 0.0
        batting = basic.get("batting_team", "Unknown")
        bowling = basic.get("bowling_team", "Unknown")
    else:
        runs = wickets = 0
        overs = 0.0
        batting = bowling = "Unknown"

    target_score = detail.get("target", 0) if detail else 0
    inning_num = 2 if target_score > 0 else 1

    # Session predictions at all checkpoints
    session_predictions = {}
    for cp in SESSION_CHECKPOINTS:
        if overs >= cp:
            session_predictions[str(cp)] = runs  # already past
        else:
            try:
                pred = predict_session(
                    batting_team=batting,
                    bowling_team=bowling,
                    runs=runs,
                    wickets=wickets,
                    overs=overs,
                    target_over=cp,
                    inning=inning_num,
                    target_runs=target_score,
                )
                session_predictions[str(cp)] = int(pred["predicted_score"])
            except Exception as e:
                logger.error(f"Session predict error: {e}")
                session_predictions[str(cp)] = None

    # Winner prediction (next checkpoint)
    try:
        pred_next = predict_session(
            batting_team=batting,
            bowling_team=bowling,
            runs=runs,
            wickets=wickets,
            overs=overs,
            inning=inning_num,
            target_runs=target_score,
        )
        winner_pred = pred_next["predicted_winner"]
        win_pct = pred_next["win_percentage"]
        target_over = int(pred_next["target_over"])
    except Exception:
        winner_pred = ""
        win_pct = ""
        target_over = 20

    live_payload = {
        "batting_team": batting,
        "bowling_team": bowling,
        "runs": runs,
        "wickets": wickets,
        "overs": overs,
        "target": detail.get("target", 0) if detail else 0,
        "crr": detail.get("crr", 0) if detail else 0,
        "rrr": detail.get("rrr", 0) if detail else 0,
        "target_over": target_over,
        "predicted_winner": winner_pred,
        "win_percentage": win_pct,
        "session_predictions": session_predictions,
        "batsmen_at_crease": detail.get("batsmen_at_crease", []) if detail else [],
        "current_bowlers": detail.get("current_bowlers", []) if detail else [],
        "playing_xi": detail.get("playing_xi", {}) if detail else {},
        "partnership": detail.get("partnership", "") if detail else "",
        "last_wicket": detail.get("last_wicket", "") if detail else "",
        "recent_balls": detail.get("recent_balls", [])[:20] if detail else [],
        "innings": detail.get("innings", []) if detail else [],
        "match_title": detail.get("match_title", "") if detail else (basic.get("title", "") if basic else ""),
        "team1": detail.get("team1", {}) if detail else {},
        "team2": detail.get("team2", {}) if detail else {},
    }

    return {"status": "live", "live": live_payload, "upcoming": upcoming}


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    try:
        out = predict_session(
            batting_team=payload.batting_team,
            bowling_team=payload.bowling_team,
            runs=payload.runs,
            wickets=payload.wickets,
            overs=payload.overs,
            target_over=payload.target_over,
        )
    except FileNotFoundError as exc:
        raise HTTPException(503, "Model artifacts unavailable.") from exc
    return PredictResponse(
        batting_team=str(out["batting_team"]),
        bowling_team=str(out["bowling_team"]),
        current_runs=int(out["current_runs"]),
        wickets=int(out["wickets"]),
        overs=float(out["overs"]),
        target_over=int(out["target_over"]),
        predicted_score=int(out["predicted_score"]),
        predicted_winner=str(out["predicted_winner"]),
        win_percentage=str(out["win_percentage"]),
    )


@app.post("/simulate", response_model=SimulationResponse)
def simulate(payload: SimulateRequest = SimulateRequest()):
    try:
        rows = run_simulation(
            deliveries_path="data/raw/deliveries.csv",
            matches_path="data/raw/matches1.csv",
            save_path="data/processed/simulation_results.csv",
            match_id=payload.match_id,
        )
        stats = summarize_predictions(rows)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        logger.exception("Simulation failed: %s", exc)
        raise HTTPException(500, "Simulation failed.") from exc

    return SimulationResponse(
        total_predictions=int(stats["total_predictions"]),
        correct=int(stats["correct"]),
        wrong=int(stats["wrong"]),
        accuracy=float(stats["accuracy"]),
        predictions=[
            SessionPredictionRow(
                match_id=int(r.get("match_id", 0)),
                inning=int(r.get("inning", 0)),
                batting_team=str(r.get("batting_team", "")),
                bowling_team=str(r.get("bowling_team", "")),
                current_over=float(r.get("current_over", 0)),
                target_over=int(r.get("target_over", 0)),
                current_runs=int(r.get("current_runs", 0)),
                current_wickets=int(r.get("current_wickets", 0)),
                predicted_score=int(r["predicted_score"]) if r.get("predicted_score") is not None else None,
                actual_score=int(r.get("actual_score", 0)),
                error=float(r["error"]) if r.get("error") is not None else None,
                result=str(r["result"]) if r.get("result") is not None else None,
                predicted_winner=str(r.get("predicted_winner", "")),
                win_percentage=str(r.get("win_percentage", "")),
            )
            for r in rows
        ],
    )


@app.get("/matches", response_model=List[MatchInfo])
def list_matches():
    try:
        matches = get_available_matches()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return [
        MatchInfo(
            match_id=int(m["match_id"]),
            season=str(m["season"]),
            team1=str(m["team1"]),
            team2=str(m["team2"]),
            winner=str(m.get("winner", "")),
            venue=str(m.get("venue", "")),
            label=str(m["label"]),
        )
        for m in matches
    ]


# ── Serve frontend ───────────────────────────────────────────────────────
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
