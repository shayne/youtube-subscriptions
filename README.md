# YouTube subscriptions viewer

A local web app that displays your YouTube subscription videos sorted by relative performance. The performance score is calculated using an algorithm that considers:

1. Base performance relative to channel average (50% weight)

   - How well a video performs compared to the channel's typical view count
   - Helps identify standout videos within each channel's context

2. Subscriber reach bonus (50% weight, only applied when positive)

   - Only kicks in when a video's views exceed the channel's subscriber count
   - No penalty for videos with fewer views than subscribers
   - Calculated as (views/subscribers)^1.2 to reward exceptional performance

3. Absolute views multiplier
   - Non-linear scaling based on total view count
   - Calculated as (1.0 + (views^0.5 / 1000000)^0.4)
   - Gives additional weight to videos with high absolute view counts

This scoring system helps surface exceptional videos while:

- Identifying breakout videos that exceed subscriber counts
- Not penalizing channels with legacy subscriber bases
- Rewarding videos that outperform their channel's average
- Giving extra weight to videos with high absolute view counts

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
