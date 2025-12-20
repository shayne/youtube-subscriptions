import os
import sqlite3
from importlib import resources
from pathlib import Path

class YouTubeDB:
    db: sqlite3.Connection

    def __init__(self, db_path: str | None = None):
        self.db_path = resolve_db_path(db_path)
        self.setup_database()
    
    def setup_database(self):
        """Initialize SQLite database for caching"""
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        cursor = self.db.cursor()
        
        # Check if tables already exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name IN ('videos', 'channels')
        """)
        existing_tables = {row[0] for row in cursor.fetchall()}
        required_tables = {'videos', 'channels'}
        
        # Only initialize if tables are missing
        if not required_tables.issubset(existing_tables):
            schema_text = (
                resources.files("ytsubs")
                .joinpath("schema.sql")
                .read_text(encoding="utf-8")
            )
            cursor.executescript(schema_text)
            self.db.commit()

    def get_last_video_date(self):
        """Get the most recent video date from the database"""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT published_date 
            FROM videos 
            ORDER BY published_date DESC 
            LIMIT 1
        ''')
        return cursor.fetchone()

    def get_tracked_channels(self):
        """Get list of channels we're tracking"""
        cursor = self.db.cursor()
        cursor.execute('SELECT id, url FROM channels')
        return cursor.fetchall()

    def update_channel_subscriber_count(self, channel_id, sub_count):
        """Update subscriber count for a channel"""
        cursor = self.db.cursor()
        cursor.execute('''
            UPDATE channels 
            SET subscriber_count = ?, last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (sub_count, channel_id))
        self.db.commit()

    def update_video_and_channel(self, video_info):
        """Update or insert video and channel information"""
        cursor = self.db.cursor()
        
        try:
            # Extract channel ID from URL
            channel_url = video_info.get('channel_url', '')
            channel_id = None
            
            # Try to extract channel ID from URL
            if '/channel/' in channel_url:
                channel_id = channel_url.split('/channel/')[1].split('?')[0]
            elif '@' in channel_url:
                # For URLs with handles like @username
                handle = channel_url.split('@')[1].split('/')[0]
                # Look up channel ID by handle
                cursor.execute('SELECT id FROM channels WHERE handle = ?', (handle,))
                result = cursor.fetchone()
                if result:
                    channel_id = result[0]
            
            if not channel_id:
                print(f"Could not extract channel ID from URL: {channel_url}")
                return
            
            # First ensure channel exists
            cursor.execute('SELECT id FROM channels WHERE id = ?', (channel_id,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO channels (id, name, url)
                    VALUES (?, ?, ?)
                ''', (
                    channel_id,
                    video_info.get('channel_name', ''),
                    channel_url
                ))
            
            # Extract video ID from URL
            video_url = video_info.get('url', '')
            video_id = None
            if 'v=' in video_url:
                video_id = video_url.split('v=')[1].split('&')[0]
            
            if not video_id:
                print(f"Could not extract video ID from URL: {video_url}")
                return
            
            # Update or insert video
            cursor.execute('''
                INSERT OR REPLACE INTO videos 
                (id, channel_id, title, url, thumbnail, views, published_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                video_id,
                channel_id,
                video_info.get('title', ''),
                video_url,
                video_info.get('thumbnail', ''),
                video_info.get('views', 0),
                video_info.get('publish_date')
            ))
            
            self.db.commit()
            
        except Exception as e:
            print(f"Error updating video: {e}")
            self.db.rollback()

    def close(self):
        """Close the database connection"""
        if self.db:
            self.db.close()


def resolve_db_path(db_path: str | None = None) -> Path:
    if db_path:
        return Path(db_path).expanduser()

    state_root = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
    )
    target = state_root / "ytsubs" / "youtube.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target
