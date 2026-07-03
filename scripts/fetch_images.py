"""Fetch openly licensed Max Verstappen images from Wikimedia Commons.

This is a MANUAL-trigger workflow: run it, then review what landed in
public/images/commons/ before committing. Every image is license-checked
programmatically — only CC0, CC BY, CC BY-SA, and public domain files are
accepted — and every accepted image gets an entry in data/attributions.json,
which the site renders as visible credits.

Usage:  python scripts/fetch_images.py            # default queries
        python scripts/fetch_images.py "Max Verstappen 2021"   # custom query
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "public" / "images" / "commons"
MANIFEST = ROOT / "data" / "attributions.json"
USER_AGENT = "MV1-fan-site/0.1 (unofficial Verstappen tribute; contact in repo README)"

DEFAULT_QUERIES = [
    "Max Verstappen Toro Rosso",
    "Max Verstappen 2015",
    "Max Verstappen 2016",
    "Max Verstappen Red Bull",
    "Max Verstappen podium",
]
RESULTS_PER_QUERY = 8
DOWNLOAD_WIDTH = 1600  # px; big enough for full-bleed sections, small enough to be polite

# Accepted license short names, e.g. "CC BY 2.0", "CC BY-SA 4.0", "CC0",
# "Public domain". Anything else (incl. "Fair use", GFDL-only) is rejected.
ALLOWED_LICENSE = re.compile(r"^(cc0\b.*|public domain\b.*|cc by(-sa)? \d\.\d.*)$", re.I)


def polite_get(url: str, **kwargs) -> requests.Response:
    """GET with a courtesy delay and patient 429 retries — Wikimedia's
    thumbnail servers throttle bursts of image renders hard. This workflow
    is manual and rare, so slow-and-polite beats fast-and-blocked."""
    waits = (45, 90, 180)
    for attempt in range(len(waits) + 1):
        time.sleep(4)
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60, **kwargs)
        if response.status_code == 429 and attempt < len(waits):
            print(f"  rate limited (429) — pausing {waits[attempt]}s...", flush=True)
            time.sleep(waits[attempt])
            continue
        response.raise_for_status()
        return response
    raise AssertionError("unreachable")


def api_get(params: dict) -> dict:
    return polite_get(API, params={**params, "format": "json"}).json()


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def slugify(title: str) -> str:
    """'File:Max Verstappen 2016.jpg' -> 'max-verstappen-2016.jpg'"""
    name = re.sub(r"^File:", "", title)
    stem, dot, ext = name.rpartition(".")
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return f"{slug}.{ext.lower()}"


def search_commons(query: str) -> list[dict]:
    data = api_get({
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6,  # File: namespace
        "gsrlimit": RESULTS_PER_QUERY,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size|mime",
        "iiurlwidth": DOWNLOAD_WIDTH,
    })
    return list((data.get("query") or {}).get("pages", {}).values())


def evaluate(page: dict) -> tuple[dict, str] | tuple[None, str]:
    """Return (manifest_entry, 'ok') for an acceptable image, else (None, reason)."""
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}

    def field(name: str) -> str:
        return strip_html((meta.get(name) or {}).get("value", ""))

    license_name = field("LicenseShortName")
    if not ALLOWED_LICENSE.match(license_name):
        return None, f"license not allowed: {license_name or 'unknown'}"
    if info.get("mime") not in ("image/jpeg", "image/png"):
        return None, f"unsupported mime: {info.get('mime')}"
    author = field("Artist")
    if not author:
        return None, "no author metadata"

    return {
        "file": slugify(page["title"]),
        "title": re.sub(r"^File:", "", page["title"]),
        "author": author,
        "license": license_name,
        "licenseUrl": (meta.get("LicenseUrl") or {}).get("value") or None,
        "sourceUrl": info["descriptionurl"],
        "width": info.get("thumbwidth") or info.get("width"),
        "height": info.get("thumbheight") or info.get("height"),
        "_downloadUrl": info.get("thumburl") or info["url"],
    }, "ok"


def main() -> int:
    queries = sys.argv[1:] or DEFAULT_QUERIES
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    # Existing manifest entries survive as long as their file is still on
    # disk — deleting a rejected image and re-running cleans the manifest.
    existing = []
    if MANIFEST.exists():
        existing = json.loads(MANIFEST.read_text(encoding="utf-8"))["images"]
    entries = {e["file"]: e for e in existing if (IMG_DIR / e["file"]).exists()}

    def write_manifest() -> None:
        manifest = {"images": sorted(entries.values(), key=lambda e: e["file"])}
        MANIFEST.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    seen_titles: set[str] = set()
    for query in queries:
        print(f'Searching Commons: "{query}"', flush=True)
        for page in search_commons(query):
            if page["title"] in seen_titles:
                continue
            seen_titles.add(page["title"])
            entry, reason = evaluate(page)
            if entry is None:
                print(f"  skip  {page['title']} — {reason}")
                continue
            download_url = entry.pop("_downloadUrl")
            target = IMG_DIR / entry["file"]
            if target.exists():
                # Already downloaded (possibly by an interrupted run whose
                # manifest write never happened) — register, don't re-fetch.
                if entry["file"] not in entries:
                    entries[entry["file"]] = entry
                    write_manifest()
                print(f"  have  {entry['file']}")
                continue
            try:
                target.write_bytes(polite_get(download_url).content)
            except requests.HTTPError as exc:
                # One stubborn file must not kill the whole run.
                print(f"  skip  {entry['file']} — download failed ({exc})")
                continue
            entries[entry["file"]] = entry
            print(f"  saved {entry['file']}  [{entry['license']}, {entry['author'][:40]}]")
            # Write after every save so an interrupted run loses nothing.
            write_manifest()

    write_manifest()
    print(f"\n{len(entries)} approved image(s) in manifest. Review public/images/commons/ before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
