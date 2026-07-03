"""Find official YouTube race-highlight video IDs for races that have a
result but no video yet, and store them in data/seasons/<year>.json.

Requires YOUTUBE_API_KEY in .env (or the environment). Searches are
restricted to the official FORMULA 1 channel — nothing else is accepted.

youtubeVideoId semantics in season files:
    null  -> never searched            (this script will search)
    ""    -> searched, nothing found   (skipped; delete the "" to retry)
    "abc" -> found                     (skipped forever)

Quota reality check: one YouTube search costs 100 quota units and the free
daily quota is 10,000 — about 100 searches/day. The one-time backfill of
~240 races therefore takes ~3 daily runs (the script stops cleanly at the
limit and picks up where it left off — idempotent by design). After the
backfill, a weekly run needs only 1–2 searches.

Usage:  python scripts/update_highlights.py [--limit N]   (default 90)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[1]
SEASONS_DIR = ROOT / "data" / "seasons"

F1_CHANNEL_ID = "UCB_qr75-ydFVKSF9Dmo6izg"  # FORMULA 1 official
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
USER_AGENT = "MV1-fan-site-data-script/0.1 (unofficial Verstappen tribute site)"


def search_official_highlight(api_key: str, season: int, race_name: str) -> str | None:
    """Return the best official highlight video ID for a race, or None."""
    query = f"{season} {race_name} highlights"
    response = requests.get(
        SEARCH_URL,
        params={
            "key": api_key,
            "part": "snippet",
            "channelId": F1_CHANNEL_ID,  # API-side restriction to the official channel
            "q": query,
            "type": "video",
            "maxResults": 8,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if response.status_code == 403:
        # Almost always quotaExceeded — signal the caller to stop for today.
        raise QuotaExceeded(response.json().get("error", {}).get("message", "403"))
    response.raise_for_status()

    items = response.json().get("items", [])

    def score(item: dict) -> int:
        title = item["snippet"]["title"].lower()
        points = 0
        if "highlights" in title:
            points += 4
        if "race highlights" in title:
            points += 4  # prefer the canonical "Race Highlights | ..." uploads
        if str(season) in title:
            points += 2
        # Reject sprint/qualifying/F2/F3 videos for the race slot.
        if any(word in title for word in ("qualifying", "sprint", "f2", "f3", "press conference")):
            points -= 10
        return points

    best = max(items, key=score, default=None)
    if best and score(best) >= 6:
        return best["id"]["videoId"]
    return None


class QuotaExceeded(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=90,
                        help="max searches this run (stay under daily quota)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("YOUTUBE_API_KEY is not set (in .env or the environment). Aborting.")
        return 1

    searches = found = 0
    for season_file in sorted(SEASONS_DIR.glob("*.json")):
        data = json.loads(season_file.read_text(encoding="utf-8"))
        changed = False
        for race in data["races"]:
            if race["upcoming"] or race["youtubeVideoId"] is not None:
                continue
            if searches >= args.limit:
                break
            searches += 1
            try:
                video_id = search_official_highlight(api_key, data["season"], race["raceName"])
            except QuotaExceeded as exc:
                print(f"YouTube quota exhausted ({exc}). Progress is saved — rerun tomorrow.")
                searches = args.limit
                break
            race["youtubeVideoId"] = video_id or ""
            changed = True
            if video_id:
                found += 1
                print(f"  {data['season']} {race['raceName']}: {video_id}")
            else:
                print(f"  {data['season']} {race['raceName']}: no official highlight found")
        if changed:
            season_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    print(f"\n{searches} search(es), {found} video(s) stored.")
    if searches >= args.limit:
        print("Hit the per-run limit — rerun tomorrow to continue the backfill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
