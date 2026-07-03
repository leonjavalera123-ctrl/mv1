"""Pull Max Verstappen's complete F1 race history from the Jolpica API and
write the JSON files the site is built from:

    data/seasons/<year>.json  — every race that season: results + upcoming
    data/driver.json          — bio and career totals

Run it any time:  python scripts/update_results.py

Idempotency rules this script guarantees:
- youtubeVideoId values already present in season files are preserved
  (they belong to update_highlights.py, not to this script).
- Files are rewritten only when their content actually changes, so a
  no-op run produces a clean `git status`.
- No timestamps are embedded in the data files — "last updated" comes
  from git/build time instead, otherwise every run would dirty the repo.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

from jolpica_client import fetch_all_pages, get_json

DRIVER_ID = "max_verstappen"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEASONS_DIR = DATA_DIR / "seasons"


def to_number(text):
    """API numbers arrive as strings; points can be fractional (half-points
    races like Spa 2021), so keep floats only when actually fractional."""
    value = float(text)
    return int(value) if value.is_integer() else value


def race_rows(response: dict) -> list:
    return response["MRData"]["RaceTable"]["Races"]


def fetch_results() -> list:
    print("Fetching race results...")
    return fetch_all_pages(f"drivers/{DRIVER_ID}/results.json", race_rows)


def fetch_qualifying_positions() -> dict:
    """Map (season, round) -> qualifying position. Pole = P1 in qualifying,
    which is not always the same as starting on grid slot 1 (penalties)."""
    print("Fetching qualifying results...")
    rows = fetch_all_pages(f"drivers/{DRIVER_ID}/qualifying.json", race_rows)
    positions = {}
    for race in rows:
        quali = race["QualifyingResults"][0]
        positions[(int(race["season"]), int(race["round"]))] = int(quali["position"])
    return positions


def fetch_standing_after(season: int, rnd: int) -> dict | None:
    """Championship position/points after a given round. Standings for a
    completed round are immutable, so these responses cache forever."""
    data = get_json(f"{season}/{rnd}/driverStandings.json?limit=100")
    lists = data["MRData"]["StandingsTable"]["StandingsLists"]
    if not lists:
        return None
    for entry in lists[0]["DriverStandings"]:
        if entry["Driver"]["driverId"] == DRIVER_ID:
            # Drivers tied on zero points are unranked: positionText is "-"
            # and the "position" key is absent (seen after 2015 round 1).
            position_text = entry.get("positionText", "")
            return {
                "position": int(position_text) if position_text.isdigit() else None,
                "points": to_number(entry["points"]),
            }
    return None


def build_race_entry(race: dict, quali_positions: dict) -> dict:
    """Convert one API race row into our site schema."""
    season, rnd = int(race["season"]), int(race["round"])
    result = race["Results"][0]
    position_text = result["positionText"]  # "1".."20", or "R"/"D"/"W" for DNF etc.
    finished = position_text.isdigit()
    quali = quali_positions.get((season, rnd))
    return {
        "round": rnd,
        "raceName": race["raceName"],
        "circuit": race["Circuit"]["circuitName"],
        "locality": race["Circuit"]["Location"]["locality"],
        "country": race["Circuit"]["Location"]["country"],
        "date": race["date"],
        "wikipediaUrl": race.get("url"),
        "team": result["Constructor"]["name"],
        "qualifying": quali,
        "grid": int(result["grid"]),
        "finish": int(position_text) if finished else None,
        "positionText": position_text,
        "status": result["status"],
        "points": to_number(result["points"]),
        "win": position_text == "1",
        "podium": finished and int(position_text) <= 3,
        "pole": quali == 1,
        "fastestLap": result.get("FastestLap", {}).get("rank") == "1",
        "standingAfter": fetch_standing_after(season, rnd),
        "youtubeVideoId": None,  # filled by update_highlights.py, preserved below
        "upcoming": False,
    }


def build_upcoming_entry(race: dict) -> dict:
    """A scheduled race that has no Verstappen result yet."""
    return {
        "round": int(race["round"]),
        "raceName": race["raceName"],
        "circuit": race["Circuit"]["circuitName"],
        "locality": race["Circuit"]["Location"]["locality"],
        "country": race["Circuit"]["Location"]["country"],
        "date": race["date"],
        "wikipediaUrl": race.get("url"),
        "team": None,
        "qualifying": None,
        "grid": None,
        "finish": None,
        "positionText": None,
        "status": None,
        "points": None,
        "win": False,
        "podium": False,
        "pole": False,
        "fastestLap": False,
        "standingAfter": None,
        "youtubeVideoId": None,
        "upcoming": True,
    }


def existing_video_ids(season_file: Path) -> dict:
    """Read round -> youtubeVideoId from a previously written season file."""
    if not season_file.exists():
        return {}
    data = json.loads(season_file.read_text(encoding="utf-8"))
    return {
        r["round"]: r["youtubeVideoId"]
        for r in data.get("races", [])
        if r.get("youtubeVideoId")
    }


def write_json_if_changed(path: Path, data: dict) -> bool:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    results = fetch_results()
    quali_positions = fetch_qualifying_positions()

    # Group completed races by season.
    seasons: dict[int, list] = {}
    print(f"Building race entries ({len(results)} races, standings fetched per round)...", flush=True)
    for i, race in enumerate(results, 1):
        season = int(race["season"])
        seasons.setdefault(season, []).append(build_race_entry(race, quali_positions))
        if i % 25 == 0 or i == len(results):
            print(f"  {i}/{len(results)} races processed (season {season})", flush=True)

    # The current season's calendar gives us "coming soon" cards for rounds
    # that have not produced a result yet. Never cached: the calendar can change.
    schedule = race_rows(get_json("current.json?limit=100", use_cache=False))
    if schedule:
        current_year = int(schedule[0]["season"])
        completed_rounds = {r["round"] for r in seasons.get(current_year, [])}
        for race in schedule:
            if int(race["round"]) not in completed_rounds:
                seasons.setdefault(current_year, []).append(build_upcoming_entry(race))
        seasons[current_year].sort(key=lambda r: r["round"])
    else:
        current_year = max(seasons)

    # Write one file per season.
    changed_files = []
    career = {"raceStarts": 0, "wins": 0, "podiums": 0, "poles": 0,
              "fastestLaps": 0, "points": 0, "championshipSeasons": []}
    for season in sorted(seasons):
        races = seasons[season]
        completed = [r for r in races if not r["upcoming"]]
        season_complete = season < current_year or not any(r["upcoming"] for r in races)
        last_standing = completed[-1]["standingAfter"] if completed else None
        # The standing after a season's final round IS the final championship
        # result, so no extra API call is needed to detect title wins.
        is_champion = bool(
            season_complete and last_standing and last_standing["position"] == 1
        )

        summary = {
            "championshipPosition": last_standing["position"] if last_standing else None,
            "championshipPoints": last_standing["points"] if last_standing else 0,
            "isChampion": is_champion,
            "wins": sum(r["win"] for r in completed),
            "podiums": sum(r["podium"] for r in completed),
            "poles": sum(r["pole"] for r in completed),
            "fastestLaps": sum(r["fastestLap"] for r in completed),
            "racesEntered": len(completed),
            "seasonComplete": season_complete,
        }

        # Teams in the order Max drove for them that season (mid-season
        # promotion in 2016 means a season can have two).
        teams = list(dict.fromkeys(r["team"] for r in completed if r["team"]))

        season_file = SEASONS_DIR / f"{season}.json"
        video_ids = existing_video_ids(season_file)
        for r in races:
            r["youtubeVideoId"] = video_ids.get(r["round"])

        if write_json_if_changed(season_file, {
            "season": season, "teams": teams, "summary": summary, "races": races,
        }):
            changed_files.append(season_file.name)

        career["raceStarts"] += summary["racesEntered"]
        career["wins"] += summary["wins"]
        career["podiums"] += summary["podiums"]
        career["poles"] += summary["poles"]
        career["fastestLaps"] += summary["fastestLaps"]
        career["points"] += summary["championshipPoints"]
        if is_champion:
            career["championshipSeasons"].append(season)

    career["championships"] = len(career["championshipSeasons"])
    career["seasons"] = sorted(seasons)
    career["points"] = to_number(str(career["points"]))

    bio = get_json(f"drivers/{DRIVER_ID}.json")["MRData"]["DriverTable"]["Drivers"][0]
    if write_json_if_changed(DATA_DIR / "driver.json", {
        "driver": {
            "name": f"{bio['givenName']} {bio['familyName']}",
            "code": bio.get("code"),
            "number": int(bio["permanentNumber"]) if bio.get("permanentNumber") else None,
            "nationality": bio.get("nationality"),
            "dateOfBirth": bio.get("dateOfBirth"),
            "wikipediaUrl": bio.get("url"),
        },
        "career": career,
    }):
        changed_files.append("driver.json")

    if changed_files:
        print(f"Updated {len(changed_files)} file(s): {', '.join(changed_files)}")
    else:
        print("No changes — data already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
