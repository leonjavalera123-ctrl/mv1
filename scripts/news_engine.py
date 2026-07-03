"""Aggregate Max Verstappen news from RSS feeds into data/news.json.

Pipeline: fetch feeds -> keep items that mention Verstappen -> score
(title mention > body mention, recency decay, source weight) -> dedupe
near-identical stories across outlets -> write the top 8.

The site links OUT to every story; we store only the headline and a
one-line snippet from the feed's own syndication summary — never article
body text.

To add a feed: append to FEEDS below (name, url, weight 0–1 for source
authority) — nothing else to change.

Runs daily at 12:00 UTC via GitHub Actions; also fine to run by hand:
    python scripts/news_engine.py
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news.json"
USER_AGENT = "MV1-fan-site-news/0.1 (unofficial Verstappen tribute site)"

FEEDS = [
    {"name": "Formula1.com", "url": "https://www.formula1.com/en/latest/all.xml", "weight": 1.0},
    {"name": "Autosport", "url": "https://www.autosport.com/rss/f1/news/", "weight": 0.9},
    {"name": "Motorsport.com", "url": "https://www.motorsport.com/rss/f1/news/", "weight": 0.85},
    {"name": "The Race", "url": "https://www.the-race.com/category/formula-1/feed/", "weight": 0.9},
    # PlanetF1 has RSS disabled as of 2026-07 (site is WordPress but /feed
    # 404s) — re-add here if they restore it.
    # Catch-all: anything the dedicated feeds missed. Low weight because
    # quality varies and headlines get rewritten by aggregation.
    {
        "name": "Google News",
        "url": "https://news.google.com/rss/search?q=%22Max+Verstappen%22&hl=en-US&gl=US&ceid=US:en",
        "weight": 0.55,
    },
]

TOP_N = 8
HALF_LIFE_HOURS = 36  # a story loses half its score every 36 hours
DEDUP_SIMILARITY = 0.55

STOPWORDS = frozenset(
    "a an and as at be but by for from has he his in is it its of on that the to was will with".split()
)


def fetch_feed(feed: dict) -> list:
    """Fetch one feed with our UA and timeout; a dead feed is a warning,
    never a crash — news must degrade gracefully outlet by outlet."""
    try:
        response = requests.get(feed["url"], headers={"User-Agent": USER_AGENT}, timeout=20)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        print(f"  {feed['name']}: {len(parsed.entries)} items")
        return parsed.entries
    except Exception as exc:  # noqa: BLE001 — any feed failure is non-fatal
        print(f"  {feed['name']}: FAILED ({exc})")
        return []


def clean_text(raw: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", raw or "")).replace("\xa0", " ").strip()


def one_liner(raw_summary: str, limit: int = 180) -> str:
    """First sentence of the feed's syndication snippet, hard-capped."""
    text = re.sub(r"\s+", " ", clean_text(raw_summary))
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return sentence[: limit - 1] + "…" if len(sentence) > limit else sentence


def published_utc(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
    return None


def score(entry, feed: dict, now: datetime) -> float | None:
    """None = not a Verstappen story. Otherwise: mention placement x source
    weight x exponential recency decay."""
    title = clean_text(entry.get("title", "")).lower()
    summary = clean_text(entry.get("summary", "")).lower()

    if "verstappen" in title:
        base = 10.0
    elif "verstappen" in summary:
        base = 4.0
    else:
        return None

    published = published_utc(entry)
    age_hours = (now - published).total_seconds() / 3600 if published else 96.0
    recency = 0.5 ** (max(age_hours, 0) / HALF_LIFE_HOURS)
    return base * feed["weight"] * recency


def title_tokens(title: str) -> frozenset:
    words = re.findall(r"[a-z0-9']+", title.lower())
    return frozenset(w for w in words if w not in STOPWORDS)


def similar(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main() -> int:
    now = datetime.now(timezone.utc)

    print("Fetching feeds...")
    candidates = []
    for feed in FEEDS:
        for entry in fetch_feed(feed):
            item_score = score(entry, feed, now)
            if item_score is None or not entry.get("link"):
                continue
            published = published_utc(entry)
            headline = clean_text(entry.get("title", ""))
            summary = one_liner(entry.get("summary", ""))
            source = feed["name"]

            # Google News quirks: headlines end in " - Publisher" (surface
            # the real outlet instead), and summaries just repeat the
            # headline (drop those — an echo adds nothing).
            if source == "Google News" and " - " in headline:
                headline, source = headline.rsplit(" - ", 1)
            if summary and similar(title_tokens(summary), title_tokens(headline)) > 0.8:
                summary = ""

            candidates.append({
                "score": item_score,
                "tokens": title_tokens(headline),
                "topic": {
                    "headline": headline,
                    "summary": summary,
                    "source": source,
                    "url": entry["link"],
                    "published": published.isoformat(timespec="seconds") if published else None,
                },
            })

    # Highest score first; a lower-scored near-duplicate of a kept story
    # is dropped (same story syndicated across outlets).
    candidates.sort(key=lambda c: (-c["score"], c["topic"]["url"]))
    kept: list[dict] = []
    for candidate in candidates:
        if any(similar(candidate["tokens"], k["tokens"]) >= DEDUP_SIMILARITY for k in kept):
            continue
        kept.append(candidate)
        if len(kept) == TOP_N:
            break

    output = {"topics": [k["topic"] for k in kept]}
    text = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8") == text:
        print(f"\n{len(kept)} topics ranked — no changes to news.json.")
    else:
        OUTPUT.write_text(text, encoding="utf-8")
        print(f"\n{len(kept)} topics written to news.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
