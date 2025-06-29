# YouTube subscriptions viewer

A local web app that displays your YouTube subscription videos sorted by a sophisticated performance algorithm. The scoring system uses multiple factors to surface high-quality content while giving smaller channels a fair chance to compete.

## Ranking Algorithm

The performance score is calculated using a weighted combination of factors:

1. **Base Performance (25% weight)**
   - Compares video views to the channel's average
   - Capped at 5x to prevent extreme values
   - Helps identify standout videos within each channel's context

2. **Engagement Rate (20% weight)**
   - Rewards videos reaching 10%+ of subscribers
   - Uses square root scaling for diminishing returns
   - No penalty for videos below threshold

3. **Time Decay Factor (20% weight)**
   - Newer videos receive a boost that decays over 30 days
   - Uses quadratic decay: (1 - age_in_days/30)²
   - Helps surface fresh content before it goes viral

4. **Velocity Metric (15% weight)**
   - Measures views per hour since publication
   - Logarithmic scaling prevents extreme values
   - Identifies trending videos gaining views rapidly

5. **Channel Size Normalization (10% weight)**
   - Small channels (<100k subs): +10% bonus
   - Medium channels (100k-1M): +7% bonus
   - Large channels (1M-10M): +3% bonus
   - Helps smaller creators compete fairly

6. **Duration Adjustment (10% weight)**
   - Recognizes longer videos typically get fewer views
   - Sweet spot: 10-30 minute videos get full bonus
   - Prevents bias against long-form content

This scoring system ensures:
- Fresh content gets highlighted
- Small channels can compete with large ones
- Quality matters more than channel size
- Both short and long videos are treated fairly
- Viral outliers don't skew channel averages

## Overview

A tool to track YouTube subscriptions and surface high-performing videos. It consists of:

1. A channel stats scraper that collects subscriber counts and average views
2. A video scraper that collects new videos from subscribed channels
3. A static page generator that creates a feed of videos sorted by performance

## Setup

1. Requirements:

   - Python 3.7+
   - Google Chrome browser

2. Create Python environment and install dependencies:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### First-time setup

Run these commands in order:

```bash
python scrape_channel_stats.py  # When Chrome opens, log in to YouTube
python scrape_videos.py         # Collect recent videos
python generate_feed.py         # Generate the feed
```

Your YouTube login is saved in the `chrome_profile/` directory, so you'll only need to log in once. Subsequent runs will reuse this profile.

### Regular usage

1. Collect video data:

```bash
python scrape_videos.py  # Run daily to get new videos
```

2. Update channel statistics (subscriber counts, average views):

```bash
python scrape_channel_stats.py  # Run occasionally (e.g., monthly)
```

3. Generate the feed:

```bash
python generate_feed.py  # Creates youtube_feed.html
```

Open `youtube_feed.html` in your browser to view your subscription feed.

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

- Python 3.7+
- Google Chrome
