# YouTube subscriptions viewer

A local web app that displays your YouTube subscription videos sorted by a sophisticated performance algorithm. The scoring system uses multiple factors to surface high-quality content while giving smaller channels a fair chance to compete.

## Ranking Algorithm

The performance score is calculated using a weighted combination of factors, designed to surface exceptional videos even when the scraper is run sporadically:

1. **Base Performance (35% weight)**
   - Compares video views to the channel's average (capped at 5×)
   - Highlights true standouts within each channel's history

2. **Engagement Rate (25% weight)**
   - Rewards videos reaching 10%+ of subscribers
   - Square-root scaling to give diminishing returns without punishing lower reach

3. **Forecasted 48h Performance (20% weight)**
   - Projects total views at 48h assuming ~60% arrive in the first 8h and ~95% by 48h
   - Gives very new uploads credit for strong early velocity

4. **Velocity Metric (10% weight)**
   - Views per hour since publication, logarithmically scaled as a bonus
   - Keeps currently surging content competitive without penalizing slower burns

5. **Channel Size Normalization (7% weight)**
   - Small channels (<100k subs): +7% bonus
   - Medium channels (100k-1M): +5% bonus
   - Large channels (1M-10M): +2% bonus
   - Helps smaller creators compete fairly

6. **Duration Adjustment (3% weight)**
   - Slightly boosts videos in the 10–30 minute sweet spot
   - Keeps short/long content competitive without heavy bias

This scoring system keeps the focus on videos that outperform their channel norms, credits early momentum as a forecast (not just recency), and avoids decaying scores just because content is older when you run the scraper.

## Overview

A tool to track YouTube subscriptions and surface high-performing videos. It consists of:

1. A channel stats scraper that collects subscriber counts and average views
2. A video scraper that collects new videos from subscribed channels
3. A static page generator that creates a feed of videos sorted by performance

## Quick start (recommended: uvx)

You can run the tool directly with `uvx` — no cloning and no manual installs:

```bash
uvx ytsubs scrape-channels
uvx ytsubs scrape-videos
uvx ytsubs generate-feed
```

## Setup (local dev)

1. Requirements:

   - Python 3.12+
   - Google Chrome browser

2. (Optional) Install tool versions with mise:

```bash
mise install
```

3. Install dependencies with uv:

```bash
uv sync
```

## Usage

### First-time setup

Run these commands in order:

```bash
uv run ytsubs scrape-channels   # When Chrome opens, log in to YouTube
uv run ytsubs scrape-videos     # Collect recent videos
uv run ytsubs generate-feed     # Generate the feed
```

Your YouTube login is saved in `~/.local/state/ytsubs/chrome_profile` (or `$XDG_STATE_HOME/ytsubs/chrome_profile`), so you'll only need to log in once. Subsequent runs will reuse this profile.

### Regular usage

1. Collect video data:

```bash
uv run ytsubs scrape-videos  # Run daily to get new videos
```

2. Update channel statistics (subscriber counts, average views):

```bash
uv run ytsubs scrape-channels  # Run occasionally (e.g., monthly)
```

3. Generate the feed:

```bash
uv run ytsubs generate-feed  # Creates ytsubs_feed.html in your temp directory
```

Open the printed `ytsubs_feed.html` path in your browser to view your subscription feed.

### Data locations (XDG)

- Chrome profile: `~/.local/state/ytsubs/chrome_profile` (or `$XDG_STATE_HOME/ytsubs/chrome_profile`)
- SQLite DB: `~/.local/state/ytsubs/youtube.db` (or `$XDG_STATE_HOME/ytsubs/youtube.db`)
- Feed output (default): your temp directory (`ytsubs_feed.html`)

### Debug tooling

```bash
uv run ytsubs debug-scrape --scrolls 4 --filter "gymkhana"
```

## Development

The project uses:

- SQLite for data storage
- Playwright for web scraping
- Preact for the frontend (served statically)

## Makefile commands

The project includes several helpful make commands:

- `make clean`: Remove Python cache files
- `make reset-db`: Reset database to empty tables
- `make reset-videos`: Clear only the videos table
- `make reset-channels`: Clear only the channels table

## Requirements

- Python 3.12+
- Google Chrome
