"""Shared client for the Jolpica F1 API (https://api.jolpi.ca/ergast/f1/).

Every data script talks to the API through this module, so three concerns
live in exactly one place:

1. Rate limiting — Jolpica allows ~4 requests/second (500/hour) for
   unauthenticated use. We keep a fixed delay between real network
   requests to stay comfortably under both limits.
2. Caching — every response is saved under data/cache/jolpica/.
   Historical F1 data never changes, so a cached response is as good as
   a fresh one, and re-running a script costs almost zero API calls.
   (If a past result is ever corrected — e.g. a penalty applied weeks
   later — delete data/cache/jolpica/ to force a full refresh.)
3. Pagination — the API returns at most 100 rows per request.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

BASE_URL = "https://api.jolpi.ca/ergast/f1"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache" / "jolpica"

# Jolpica enforces two limits for unauthenticated use: a 4 req/s burst cap
# and a 500 req/hour sustained cap (~7.2s average spacing). We start fast,
# and the first 429 response drops us to the sustained pace for the rest of
# the run. Large backfills are a one-time cost — afterwards the cache
# answers almost everything.
FAST_DELAY_SECONDS = 0.4
SUSTAINED_DELAY_SECONDS = 8.0
MAX_RETRIES = 12

USER_AGENT = "MV1-fan-site-data-script/0.1 (unofficial Verstappen tribute site)"

_last_request_at = 0.0
_current_delay = FAST_DELAY_SECONDS


def _cache_file(path: str) -> Path:
    # "2016/5/driverStandings.json?limit=100" -> "2016_5_driverStandings.json_limit_100.json"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", path)
    return CACHE_DIR / f"{safe}.json"


def read_cached(path: str) -> dict | None:
    """Return the cached response for an API path, or None if not cached."""
    cache_file = _cache_file(path)
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return None


def get_json(path: str, use_cache: bool = True) -> dict:
    """GET one API path (e.g. "drivers/max_verstappen/results.json?limit=100")
    and return the parsed JSON. Serves from cache unless told not to; every
    network response is written back to the cache."""
    if use_cache:
        cached = read_cached(path)
        if cached is not None:
            return cached

    global _last_request_at, _current_delay
    for attempt in range(MAX_RETRIES):
        # Wait out the polite-delay window measured from the previous request.
        wait = _current_delay - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)

        response = requests.get(
            f"{BASE_URL}/{path}", headers={"User-Agent": USER_AGENT}, timeout=30
        )
        _last_request_at = time.monotonic()

        if response.status_code == 429:
            # Hourly budget exhausted: honor Retry-After if given, slow all
            # subsequent requests to the sustained pace, and try again.
            _current_delay = SUSTAINED_DELAY_SECONDS
            retry_after = int(response.headers.get("Retry-After") or 0)
            pause = max(retry_after, 20 * (attempt + 1))
            print(f"  rate limited (429) — pausing {pause}s...", flush=True)
            time.sleep(pause)
            continue

        response.raise_for_status()
        data = response.json()
        break
    else:
        raise RuntimeError(f"Still rate limited after {MAX_RETRIES} attempts: {path}")

    cache_file = _cache_file(path)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def fetch_all_pages(path: str, extract_rows) -> list:
    """Fetch every page of a paginated endpoint (path must have no query
    string). `extract_rows` pulls the row list out of one response.

    Cache rule: a FULL page (100 rows) is final forever, because the API
    appends new races at the end — it never inserts into the middle. A
    PARTIAL page is the growing edge of the data, so it is refetched on
    every run to pick up new races.
    """
    rows: list = []
    limit, offset = 100, 0
    while True:
        page_path = f"{path}?limit={limit}&offset={offset}"
        cached = read_cached(page_path)
        if cached is not None and len(extract_rows(cached)) == limit:
            data = cached
        else:
            data = get_json(page_path, use_cache=False)
        rows.extend(extract_rows(data))
        total = int(data["MRData"]["total"])
        offset += limit
        if offset >= total:
            return rows
