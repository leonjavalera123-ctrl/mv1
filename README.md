# MV1 — The Max Verstappen Story

An unofficial, fan-made, single-page scroll-driven tribute site chronicling Max
Verstappen's Formula 1 career (2015–present), plus documented outings in other
motorsport. Built static-first with [Astro](https://astro.build), animated with
GSAP ScrollTrigger, and kept fresh by automated Python data pipelines running
on GitHub Actions.

> **Disclaimer:** This is an unofficial fan project. It is not affiliated with,
> endorsed by, or connected to Max Verstappen, Red Bull Racing, Oracle, or
> Formula 1. All video content is embedded from official YouTube channels via
> YouTube's iframe embed API. All images are openly licensed (CC/public domain)
> via Wikimedia Commons, with attribution.

## How the site works

```
Python scripts (scripts/)  ──write──►  JSON data (data/)  ──read at build──►  Astro site (src/)
        ▲                                                                          │
        └────────────── GitHub Actions run scripts on a schedule ──► rebuild ──► GitHub Pages
```

The site is fully static: no server, no client-side API calls. Python scripts
pull race results, highlight video IDs, news, and licensed images into JSON
files; committing updated JSON triggers a rebuild and redeploy.

## Project structure

```
mv1/
├── .github/workflows/   # scheduled data updates + deploy (Phase 5)
├── data/                # JSON consumed by the site at build time
│   ├── cache/           # raw API response cache (gitignored)
│   ├── seasons/         # one JSON file per season: races, results, video IDs
│   ├── driver.json      # career totals: wins, poles, titles, podiums
│   ├── news.json        # ranked Verstappen news topics (auto-generated)
│   ├── other-motorsport.json  # hand-edited non-F1 appearances
│   └── attributions.json      # image license/attribution manifest
├── public/
│   └── images/commons/  # approved Wikimedia Commons images
├── scripts/             # idempotent Python data pipelines (Phase 1 & 5)
│   ├── update_results.py     # Jolpica F1 API → data/seasons/*.json
│   ├── update_highlights.py  # YouTube Data API → video IDs in season JSON
│   ├── news_engine.py        # RSS aggregation → data/news.json
│   ├── fetch_images.py       # Wikimedia Commons → public/images + attributions
│   └── requirements.txt
├── src/
│   ├── components/      # Astro components (race cards, embeds, counters…)
│   ├── layouts/         # base HTML layout, meta/OG tags
│   ├── lib/             # shared JS/TS helpers (data loading, formatting)
│   ├── pages/           # index.astro (the single page) + attributions page
│   └── styles/          # design tokens + global CSS
├── .env.example         # template for API keys (copy to .env, never commit)
└── astro.config.mjs     # GitHub Pages site/base config
```

## Local development

```bash
# one-time setup
npm install
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r scripts/requirements.txt
copy .env.example .env                            # then fill in keys

# run the site
npm run dev
```

## Data workflows

All scripts are idempotent: running them twice in a row produces no spurious
changes, and interrupted runs resume where they stopped (API responses are
cached in `data/cache/`, which is gitignored).

| Script | What it does | Schedule (GitHub Actions) | Manual run |
|---|---|---|---|
| `update_results.py` | Pull Verstappen race results, per-round standings, and the current-season calendar from the Jolpica F1 API into `data/seasons/` + `data/driver.json` | `update-data.yml`, Mondays 06:00 UTC | `python scripts/update_results.py` |
| `update_highlights.py` | For races with a result but no video, search the official FORMULA 1 channel for race highlights and store the video ID | Same workflow, right after results | `python scripts/update_highlights.py [--limit N]` |
| `news_engine.py` | Aggregate RSS feeds, keep Verstappen stories, score (title mention > body mention, recency decay, source weight), dedupe near-identical stories, write top 8 to `data/news.json` | `update-news.yml`, daily 12:00 UTC | `python scripts/news_engine.py` |
| `fetch_images.py` | Search Wikimedia Commons, verify licenses programmatically (CC0/CC BY/CC BY-SA/public domain only), download approved images + `data/attributions.json` | `fetch-images.yml`, **manual trigger only** — opens a PR for human review | `python scripts/fetch_images.py ["query" ...]` |

**Deploy:** `deploy.yml` builds and publishes to GitHub Pages on every push to
`main`, and also after the two scheduled data workflows finish (bot pushes
don't fire `push` events, so it listens for `workflow_run` instead).

### Workflow details & gotchas

- **YouTube quota:** a search costs 100 of the 10,000 free daily units, so
  `update_highlights.py` caps itself at 90 searches per run (`--limit`). The
  one-time backfill of ~240 races takes ~3 daily runs; weekly upkeep needs
  1–2. In season JSON, `youtubeVideoId: null` means "never searched", `""`
  means "searched, nothing found" (delete the `""` to retry a race).
- **Jolpica rate limits:** 500 requests/hour sustained. The client starts
  fast and drops to ~8s spacing after the first 429. The initial history
  backfill is the only slow run; after that the cache answers everything.
- **Adding a news feed:** append `{name, url, weight}` to `FEEDS` in
  `scripts/news_engine.py`. Weight (0–1) expresses source authority. Dead
  feeds fail gracefully and are reported in the run log.
- **Image review:** `fetch-images.yml` deliberately opens a pull request
  instead of committing — review every image and its attribution entry
  before merging. To reject one, delete the image file and its entry in
  `data/attributions.json` on the PR branch.

### One-time GitHub setup

1. Create the repo and push `main`.
2. **Settings → Pages → Source: GitHub Actions.**
3. **Settings → Secrets and variables → Actions → New repository secret:**
   `YOUTUBE_API_KEY` (from Google Cloud, YouTube Data API v3).
4. Replace `GITHUB-USERNAME` in `astro.config.mjs` with the repo owner.

## Content & licensing rules

- **Video:** official YouTube iframe embeds only (F1 → Red Bull → broadcaster
  channel priority). No downloading, re-hosting, or screen captures. Embeds use
  a click-to-load facade — no iframe loads until the user clicks play.
- **Images:** Wikimedia Commons only, restricted to CC-BY / CC-BY-SA / CC0 /
  public domain, license verified programmatically. Every image renders a
  visible attribution (author, license, link). See `/attributions`.
- **Branding:** original "MV1" wordmark; no official F1 or Red Bull logos.
- **News:** headlines + one-line summaries in original words, always linking
  out to the source. Article text is never reproduced.

## Roadmap

- [x] Phase 0 — stack confirmed, repo scaffolded, env template, README
- [x] Phase 1 — Jolpica data scripts + JSON schema
- [x] Phase 2 — static site structure + design system
- [x] Phase 3 — GSAP scroll animation pass
- [x] Phase 4 — YouTube facades + Wikimedia image pipeline
- [x] Phase 5 — news engine + GitHub Actions automation
- [x] Phase 6 — performance/a11y audit (Lighthouse 99/100/100/100); deploy pending GitHub account setup

---

Built by a fan, for fans. 🧡
