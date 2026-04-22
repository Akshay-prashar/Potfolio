"""Rich ESPN Cricinfo scraper — extracts full match detail like Cricbuzz/Cricinfo.

Fetches from the match's live-cricket-score page __NEXT_DATA__ JSON to get:
- Innings scorecard (runs/wickets/overs per innings)
- Batsmen at crease (name, runs, balls, 4s, 6s, SR)
- Current bowlers (name, overs, maidens, runs, wickets, economy)
- Playing XI for both teams
- Ball-by-ball recent commentary
- Run rates (CRR, RRR)
- Partnership, last wicket, target, reviews
- Upcoming IPL fixtures
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SCHEDULE_URL = "https://www.espncricinfo.com/live-cricket-match-schedule-fixtures"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


class CricinfoScrapeError(Exception):
    pass


def _safe_int(v: Any, d: int = 0) -> int:
    try:
        return int(float(str(v).split("/")[0].split("&")[-1].strip()))
    except Exception:
        return d


def _safe_float(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return d


def _is_ipl(series_name: str) -> bool:
    if not series_name:
        return False
    low = series_name.lower()
    return "ipl" in low or "indian premier league" in low


# ─── Schedule: discover live match URL and upcoming fixtures ──────────────

def _fetch_schedule_json(timeout: int = 12) -> Dict[str, Any]:
    r = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    scr = soup.find("script", id="__NEXT_DATA__")
    if not scr or not scr.string:
        raise CricinfoScrapeError("No __NEXT_DATA__ on schedule page")
    return json.loads(scr.string)


def discover_ipl_matches(timeout: int = 12) -> Dict[str, Any]:
    """Return live match URL + upcoming list from the schedule page."""
    data = _fetch_schedule_json(timeout)
    app = data.get("props", {}).get("appPageProps", {}).get("data", {})
    matches = app.get("data", {}).get("content", {}).get("matches", [])
    if not matches:
        matches = app.get("matches", [])

    now = datetime.now(timezone.utc)
    window = now + timedelta(hours=48)

    live_match_url = None
    live_match_basic = None
    upcoming = []

    for m in matches:
        series = m.get("series", {})
        if not _is_ipl(series.get("name", "")):
            continue

        state = str(m.get("state", "")).upper()
        slug = m.get("slug", "")
        obj_id = m.get("objectId", "")
        series_slug = series.get("slug", "")
        series_obj = series.get("objectId", "")
        teams_raw = m.get("teams", [])
        if len(teams_raw) < 2:
            continue

        t1 = teams_raw[0].get("team", {})
        t2 = teams_raw[1].get("team", {})

        if state == "LIVE":
            # Build the match page URL
            live_match_url = f"https://www.espncricinfo.com/series/{series_slug}-{series_obj}/{slug}-{obj_id}/live-cricket-score"
            
            # Also grab basic score from schedule for fast display
            live_team = next((t for t in teams_raw if t.get("isLive")), teams_raw[0])
            other_team = teams_raw[1] if live_team == teams_raw[0] else teams_raw[0]
            score_str = str(live_team.get("score", "0"))
            if "&" in score_str:
                score_str = score_str.split("&")[-1].strip()
            parts = score_str.split("/")
            live_match_basic = {
                "batting_team": live_team.get("team", {}).get("name", "Unknown"),
                "bowling_team": other_team.get("team", {}).get("name", "Unknown"),
                "runs": _safe_int(parts[0] if parts else "0"),
                "wickets": _safe_int(parts[1] if len(parts) > 1 else "0"),
                "status_text": m.get("statusText", ""),
                "title": m.get("title", ""),
            }

        elif state == "PRE":
            start_str = m.get("startTime", "")
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except Exception:
                start_dt = None
            if start_dt and now <= start_dt <= window:
                upcoming.append({
                    "team1": t1.get("name", "TBD"),
                    "team2": t2.get("name", "TBD"),
                    "team1_abbr": t1.get("abbreviation", ""),
                    "team2_abbr": t2.get("abbreviation", ""),
                    "start_time": start_str,
                    "title": m.get("title", ""),
                    "venue": m.get("ground", {}).get("smallName", ""),
                    "status_text": m.get("statusText", ""),
                })

    return {
        "live_match_url": live_match_url,
        "live_match_basic": live_match_basic,
        "upcoming": upcoming,
    }


# ─── Match Detail: rich data from the match page ─────────────────────────

def _parse_batsman(b: Dict) -> Dict:
    p = b.get("player", {})
    return {
        "name": p.get("name", ""),
        "long_name": p.get("longName", ""),
        "runs": b.get("runs", 0),
        "balls": b.get("balls", 0),
        "fours": b.get("fours", 0),
        "sixes": b.get("sixes", 0),
        "strike_rate": b.get("strikeRate", 0),
        "is_batting": b.get("isBatting", False),
    }


def _parse_bowler(bo: Dict) -> Dict:
    p = bo.get("player", {})
    return {
        "name": p.get("name", ""),
        "long_name": p.get("longName", ""),
        "overs": bo.get("overs", 0),
        "maidens": bo.get("maidens", 0),
        "runs": bo.get("conceded", 0),
        "wickets": bo.get("wickets", 0),
        "economy": bo.get("economy", 0),
    }


def scrape_match_detail(match_url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """Scrape the rich match page and return structured data."""
    try:
        r = requests.get(match_url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    scr = soup.find("script", id="__NEXT_DATA__")
    if not scr or not scr.string:
        return None

    try:
        raw = json.loads(scr.string)
    except json.JSONDecodeError:
        return None

    mp = raw.get("props", {}).get("appPageProps", {}).get("data", {}).get("data", {})
    match_obj = mp.get("match", {})
    content = mp.get("content", {})

    # ── Teams from match object
    teams_raw = match_obj.get("teams", [])
    team1_info = teams_raw[0].get("team", {}) if len(teams_raw) > 0 else {}
    team2_info = teams_raw[1].get("team", {}) if len(teams_raw) > 1 else {}

    # ── Innings
    innings_list = content.get("innings", [])
    innings_data = []
    current_inning = None
    for inn in innings_list:
        team = inn.get("team", {})
        batsmen = [_parse_batsman(b) for b in inn.get("inningBatsmen", []) if b.get("runs") is not None]
        bowlers = [_parse_bowler(bo) for bo in inn.get("inningBowlers", [])]

        inn_obj = {
            "inning_number": inn.get("inningNumber", 0),
            "is_current": inn.get("isCurrent", False),
            "team_name": team.get("name", ""),
            "team_abbr": team.get("abbreviation", ""),
            "runs": inn.get("runs", 0),
            "wickets": inn.get("wickets", 0),
            "overs": _safe_float(inn.get("overs"), 0.0),
            "target": inn.get("target", 0),
            "batsmen": batsmen,
            "bowlers": bowlers,
        }
        innings_data.append(inn_obj)
        if inn.get("isCurrent"):
            current_inning = inn_obj

    # ── Live performers (batsmen at crease + current bowler)
    live_perf = content.get("livePerformance", {})
    batsmen_at_crease = [_parse_batsman(b) for b in live_perf.get("batsmen", [])]
    current_bowlers = [_parse_bowler(bo) for bo in live_perf.get("bowlers", [])]

    # ── Playing XI
    match_players = content.get("matchPlayers", {})
    team_players = match_players.get("teamPlayers", []) if isinstance(match_players, dict) else []
    playing_xi = {}
    for tg in team_players:
        tname = tg.get("team", {}).get("name", "Unknown")
        players = []
        for p in tg.get("players", []):
            pl = p.get("player", {})
            players.append({
                "name": pl.get("name", ""),
                "long_name": pl.get("longName", ""),
                "batting_style": pl.get("battingStyle", ""),
                "bowling_style": pl.get("bowlingStyle", ""),
            })
        playing_xi[tname] = players

    # ── Support info (run rates, partnership, last bat)
    support = content.get("supportInfo", {})
    live_info = support.get("liveInfo", {}) if isinstance(support, dict) else {}
    live_summary = support.get("liveSummary", {}) if isinstance(support, dict) else {}

    crr = _safe_float(live_info.get("currentRunRate"), 0.0)
    rrr = _safe_float(live_info.get("requiredRunrate"), 0.0)
    partnership = str(live_summary.get("partnershipText", "")) if isinstance(live_summary, dict) else ""
    last_wicket = str(live_summary.get("lastBatText", "")) if isinstance(live_summary, dict) else ""

    # ── Recent ball commentary
    rbc = content.get("recentBallCommentary", {})
    balls = rbc.get("ballComments", []) if isinstance(rbc, dict) else []
    recent_balls = []
    for ball in balls[:30]:
        recent_balls.append({
            "over": ball.get("oversActual", 0),
            "runs": ball.get("totalRuns", 0),
            "batsman_runs": ball.get("batsmanRuns", 0),
            "is_four": ball.get("isFour", False),
            "is_six": ball.get("isSix", False),
            "is_wicket": ball.get("isWicket", False),
            "text": str(ball.get("title", ""))[:100],
        })

    # Build the current state for predictions
    ci = current_inning or (innings_data[-1] if innings_data else {})
    batting_team = ci.get("team_name", "Unknown") if ci else "Unknown"
    bowling_team = team2_info.get("name", "Unknown") if batting_team == team1_info.get("name") else team1_info.get("name", "Unknown")

    return {
        "match_title": match_obj.get("title", ""),
        "match_status": match_obj.get("state", ""),
        "team1": {"name": team1_info.get("name", ""), "abbr": team1_info.get("abbreviation", "")},
        "team2": {"name": team2_info.get("name", ""), "abbr": team2_info.get("abbreviation", "")},
        "innings": innings_data,
        "current_inning": ci,
        "batting_team": batting_team,
        "bowling_team": bowling_team,
        "runs": ci.get("runs", 0) if ci else 0,
        "wickets": ci.get("wickets", 0) if ci else 0,
        "overs": ci.get("overs", 0.0) if ci else 0.0,
        "target": ci.get("target", 0) if ci else 0,
        "crr": crr,
        "rrr": rrr,
        "batsmen_at_crease": batsmen_at_crease,
        "current_bowlers": current_bowlers,
        "playing_xi": playing_xi,
        "partnership": partnership,
        "last_wicket": last_wicket,
        "recent_balls": recent_balls,
    }


# ─── Public API ───────────────────────────────────────────────────────────

def get_live_and_upcoming(timeout: int = 10, retries: int = 2) -> Dict[str, Any]:
    """Main entry point: discover schedule + scrape rich match detail."""
    last_err = None
    for attempt in range(max(1, retries)):
        try:
            schedule = discover_ipl_matches(timeout=timeout)

            live_url = schedule.get("live_match_url")
            detail = None
            if live_url:
                detail = scrape_match_detail(live_url, timeout=timeout)

            return {
                "live_match_url": live_url,
                "live_match_basic": schedule.get("live_match_basic"),
                "live_detail": detail,
                "upcoming": schedule.get("upcoming", []),
            }
        except Exception as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(1)

    print(f"Scraper warning: {last_err}")
    return {"live_match_url": None, "live_match_basic": None, "live_detail": None, "upcoming": []}


if __name__ == "__main__":
    out = get_live_and_upcoming()
    detail = out.get("live_detail")
    if detail:
        print(f"LIVE: {detail['batting_team']} {detail['runs']}/{detail['wickets']} ({detail['overs']})")
        print(f"CRR: {detail['crr']}  RRR: {detail['rrr']}  Target: {detail['target']}")
        print(f"At crease: {[b['name']+' '+str(b['runs'])+'('+str(b['balls'])+')' for b in detail['batsmen_at_crease']]}")
        print(f"Bowling: {[b['name']+' '+str(b['overs'])+'ov '+str(b['runs'])+'r '+str(b['wickets'])+'w' for b in detail['current_bowlers']]}")
        for tname, players in detail['playing_xi'].items():
            print(f"\n{tname}: {[p['name'] for p in players]}")
    else:
        print("No live match detail")
    print(f"\nUpcoming: {len(out['upcoming'])}")
    for u in out['upcoming'][:3]:
        print(f"  {u['team1']} vs {u['team2']} - {u['start_time']}")
