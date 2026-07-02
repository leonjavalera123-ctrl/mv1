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

*(Documented in detail as each is built — Phase 1 and Phase 5.)*

| Script | What it does | Schedule | Manual run |
|---|---|---|---|
| `update_results.py` | Pull Verstappen race results from the Jolpica F1 API into `data/seasons/` | Mondays 06:00 UTC | `python scripts/update_results.py` |
| `update_highlights.py` | Find official F1-channel highlight video IDs for races missing one | After results update | `python scripts/update_highlights.py` |
| `news_engine.py` | Aggregate, score, dedupe Verstappen news from RSS feeds → `data/news.json` | Daily 12:00 UTC | `python scripts/news_engine.py` |
| `fetch_images.py` | Fetch license-verified images from Wikimedia Commons + attribution manifest | Manual trigger only | `python scripts/fetch_images.py` |

All scripts are idempotent: running them twice in a row produces no spurious
changes.

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
- [ ] Phase 1 — Jolpica data scripts + JSON schema
- [ ] Phase 2 — static site structure + design system
- [ ] Phase 3 — GSAP scroll animation pass
- [ ] Phase 4 — YouTube facades + Wikimedia image pipeline
- [ ] Phase 5 — news engine + GitHub Actions automation
- [ ] Phase 6 — performance/a11y audit + deploy

---

Built by a fan, for fans. 🧡
