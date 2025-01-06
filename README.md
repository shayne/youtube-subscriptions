# YouTube subscriptions viewer

A local web app that displays your YouTube subscription videos sorted by relative performance. Videos are ranked using a weighted scoring system that considers:

- Video views relative to channel's average (60% weight)
- Video views relative to subscriber count (40% weight)

This helps surface videos that are performing exceptionally well compared to their channel's typical metrics, rather than just showing videos in chronological order.

## Features

- Alternative sorting based on video performance relative to channel metrics
- Time-based filtering (1 day to 1 month)
- Local database to track view count changes over time
- Automated scraping of YouTube subscription feed

## Setup

1. Create and activate a Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Browser profile & authentication

The app uses your system's installed Google Chrome browser and creates a persistent profile in the `chrome_profile/` directory. You'll need to log in to your Google account the first time you run a scraper, after which the session will be saved for future runs.

## Usage

The app consists of two scrapers and a web server:

### 1. Video scraper

```bash
python scrape_videos.py
```

This scrapes your YouTube subscriptions feed for recent videos, focusing on content from the last 30 days. Run this regularly to keep your video database updated. Each run will update existing video data rather than recreate it.

### 2. Channel statistics scraper

```bash
python scrape_channel_stats.py
```

This collects channel statistics (subscriber counts, average views, etc.). You only need to run this occasionally (e.g., weekly) to update channel metrics.

### 3. Web server

```bash
python server.py
```

Starts the web server at http://localhost:5000

## Makefile commands

The project includes several helpful make commands:

- `make clean`: Remove Python cache files
- `make reset-db`: Reset database to empty tables
- `make reset-videos`: Clear only the videos table
- `make reset-channels`: Clear only the channels table

## Requirements

- Python 3.7+
- Google Chrome
