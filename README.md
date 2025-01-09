# YouTube subscriptions viewer

A local web app that displays your YouTube subscription videos sorted by relative performance. The performance score is calculated using an adaptive algorithm that considers:

1. Base performance relative to channel average (50-80% weight)

   - Weight increases for channels with low view-to-subscriber ratios
   - Helps identify standout videos even on channels that typically get fewer views

2. Subscriber reach (20-50% weight)

   - Weight increases for channels with high view-to-subscriber ratios
   - Adapts to each channel's typical performance pattern

3. Viral bonus multiplier
   - Non-linear logarithmic scaling when a video exceeds the channel's typical view-to-subscriber ratio
   - Higher bonus (0.8x) for significantly overperforming videos
   - Lower bonus (0.4x) for slightly overperforming videos

This adaptive scoring system helps surface exceptional videos while accounting for different channel sizes and typical performance patterns. It's particularly good at identifying:

- Breakout videos from smaller channels
- Viral hits that exceed a channel's usual performance
- Consistently high-performing videos from larger channels

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
