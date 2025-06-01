CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    youtube_id TEXT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    handle TEXT,
    description TEXT,
    subscriber_count INTEGER DEFAULT 0,
    thumbnail_url TEXT,
    is_verified BOOLEAN DEFAULT 0,
    average_views INTEGER DEFAULT 0,
    last_updated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    published_date TIMESTAMP,
    thumbnail TEXT,
    duration TEXT,
    discovered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels(id)
);

CREATE INDEX IF NOT EXISTS idx_videos_published_date ON videos(published_date);
CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id); 