"""Reusable orchestration for scraping + live prediction."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

from inference import predict_live
from scraper import CricinfoScrapeError, find_live_ipl_match_url, scrape_live_match


def get_live_prediction(match_url: Optional[str] = None, timeout: int = 12) -> Dict[str, Any]:
    """
    Fetch live match data from Cricinfo and return model predictions.

    Steps:
    1. Fetch data using scraper
    2. Pass data to predict_live
    3. Return unified prediction payload
    """
    live_data = scrape_live_match(url=match_url, timeout=timeout)
    if live_data is None:
        return {"live_data": None, "prediction": None, "derived_features": {}}

    prediction = predict_live(
        batting_team=live_data["batting_team"],
        bowling_team=live_data["bowling_team"],
        runs=live_data["runs"],
        wickets=live_data["wickets"],
        overs=live_data["overs"],
    )

    return {
        "live_data": live_data,
        "prediction": prediction.get("predictions", prediction),
        "derived_features": prediction.get("derived_features", {}),
    }


def _completed_overs(overs: float) -> int:
    """Convert over notation (e.g., 10.2) to completed overs count."""
    whole = int(overs)
    balls = int(round((overs - whole) * 10))
    return whole + (1 if balls >= 6 else 0)


def _print_pretty_update(
    batting: str,
    bowling: str,
    runs: int,
    wickets: int,
    overs: float,
    match_status: str,
    predicted_winner: Optional[str],
    win_percentage: Optional[str],
    predicted_score: Optional[float],
    target_over: int,
    is_extra: bool = False,
    reason: Optional[str] = None,
) -> None:
    """Print clean, timestamped live prediction output."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = "[EXTRA UPDATE]" if is_extra else "[UPDATE]"

    print(f"\n[{timestamp}] {prefix}")
    if reason:
        print(f"Reason: {reason}")
    print(f"Match Status: {match_status}")
    print(f"Match: {batting} vs {bowling}")
    print(f"Score: {runs}/{wickets} ({overs})")

    winner_label = predicted_winner or "N/A"
    percent_label = win_percentage or "N/A"
    score_label = int(round(float(predicted_score))) if predicted_score is not None else "N/A"

    print(f"Predicted Winner: {winner_label} ({percent_label})")
    print(f"Predicted Score ({target_over} overs): {score_label}")


def run_live_prediction_loop(match_url: Optional[str] = None, interval_seconds: int = 30) -> None:
    """
    Poll live score every `interval_seconds`, run predictions, and print updates.

    Extra updates are printed when:
    - wickets increase
    - over milestones are reached (6, 10, 15, 20)
    """
    no_match_interval_seconds = 60
    match_interval_seconds = max(5, interval_seconds)
    milestones = (6, 10, 15, 20)
    triggered_milestones: set[int] = set()
    previous_wickets: int | None = None
    active_match_url = match_url

    if active_match_url:
        print(f"Starting live prediction loop for URL: {active_match_url}")
    else:
        print("Starting live prediction loop in AUTO mode.")
    print(f"No-match retry interval: {no_match_interval_seconds}s")
    print(f"Live update interval: {match_interval_seconds}s")

    while True:
        try:
            # Auto-discover live IPL match URL when not pinned.
            if active_match_url is None:
                discovered = find_live_ipl_match_url(retries=3, retry_delay=10, timeout=12)
                if not discovered:
                    now = datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] No live IPL match currently")
                    time.sleep(no_match_interval_seconds)
                    continue
                active_match_url = discovered
                triggered_milestones.clear()
                previous_wickets = None

            result = get_live_prediction(match_url=active_match_url)
            if result.get("live_data") is None:
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] Match finished or not live anymore. Waiting for next live IPL match.")
                active_match_url = None if match_url is None else match_url
                time.sleep(no_match_interval_seconds)
                continue

            live_data = result["live_data"]
            pred = result["prediction"]
            match_status = str(live_data.get("match_status", "live"))
            if match_status != "live":
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] Match status: {match_status}. Stopping current match tracking.")
                active_match_url = None if match_url is None else match_url
                time.sleep(no_match_interval_seconds)
                continue

            batting = live_data.get("batting_team", "Unknown")
            bowling = live_data.get("bowling_team", "Unknown")
            runs = live_data.get("runs", 0)
            wickets = int(live_data.get("wickets", 0))
            overs = float(live_data.get("overs", 0.0))
            completed = _completed_overs(overs)

            win_prob = pred.get("batting_team_win_probability")
            score = pred.get("predicted_score")
            predicted_winner = pred.get("predicted_winner")
            win_percentage = pred.get("win_percentage")
            target_over = int(pred.get("target_over", 20))

            # Backward-compatible fallback if old prediction format is loaded.
            if predicted_winner is None:
                predicted_winner = batting if (win_prob is not None and float(win_prob) >= 0.5) else bowling
            if win_percentage is None and win_prob is not None:
                p = float(win_prob)
                win_percentage = f"{int(round((p if p >= 0.5 else 1 - p) * 100))}%"

            _print_pretty_update(
                batting=batting,
                bowling=bowling,
                runs=int(runs),
                wickets=wickets,
                overs=overs,
                match_status=match_status,
                predicted_winner=predicted_winner,
                win_percentage=win_percentage,
                predicted_score=score,
                target_over=target_over,
            )

            # Extra update on wicket.
            if previous_wickets is not None and wickets > previous_wickets:
                _print_pretty_update(
                    batting=batting,
                    bowling=bowling,
                    runs=int(runs),
                    wickets=wickets,
                    overs=overs,
                    match_status=match_status,
                    predicted_winner=predicted_winner,
                    win_percentage=win_percentage,
                    predicted_score=score,
                    target_over=target_over,
                    is_extra=True,
                    reason="Wicket detected",
                )

            # Extra updates on over milestones.
            for milestone in milestones:
                if completed >= milestone and milestone not in triggered_milestones:
                    triggered_milestones.add(milestone)
                    _print_pretty_update(
                        batting=batting,
                        bowling=bowling,
                        runs=int(runs),
                        wickets=wickets,
                        overs=overs,
                        match_status=match_status,
                        predicted_winner=predicted_winner,
                        win_percentage=win_percentage,
                        predicted_score=score,
                        target_over=target_over,
                        is_extra=True,
                        reason=f"Over milestone reached: {milestone}",
                    )

            previous_wickets = wickets
        except CricinfoScrapeError as exc:
            # No live match or temporary fetch issue: keep polling quietly.
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] [INFO] {exc}")
            active_match_url = None if match_url is None else match_url
            time.sleep(no_match_interval_seconds)
            continue
        except Exception as exc:  # pylint: disable=broad-except
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] [ERROR] Loop iteration failed: {exc}")
            time.sleep(no_match_interval_seconds)
            continue

        time.sleep(match_interval_seconds)


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else None
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    try:
        run_live_prediction_loop(match_url=url, interval_seconds=interval)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Live prediction failed: {exc}")
        raise SystemExit(2)
