import sqlite3
from datetime import datetime, timedelta
import re
import os

class YouTubeDB:
    def __init__(self, db_path='youtube.db'):
        self.db_path = db_path
        self.db = None
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
            # Read and execute schema.sql
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_path, 'r') as f:
                cursor.executescript(f.read())
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

    def get_videos_with_performance(self):
        """Get videos with performance metrics for reporting"""
        cursor = self.db.cursor()
        
        cursor.execute('''
            WITH ChannelStats AS (
                SELECT 
                    channel_id,
                    AVG(views) as avg_views,
                    MAX(views) as max_views
                FROM videos
                WHERE published_date >= datetime('now', '-30 days')
                GROUP BY channel_id
            )
            SELECT 
                v.*, 
                c.name as channel_name, 
                c.url as channel_url,
                c.subscriber_count,
                cs.avg_views as channel_avg_views,
                cs.max_views as channel_max_views,
                CASE 
                    WHEN c.subscriber_count > 0 THEN (
                        (v.views * 1.0 / c.subscriber_count) * 0.4 +
                        (v.views * 1.0 / NULLIF(cs.avg_views, 0)) * 0.4 +
                        (v.views * 1.0 / NULLIF(cs.max_views, 0)) * 0.2
                    )
                    ELSE 0 
                END as performance_score
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            LEFT JOIN ChannelStats cs ON v.channel_id = cs.channel_id
            WHERE v.published_date >= datetime('now', '-30 days')
            ORDER BY performance_score DESC
        ''')
        
        return cursor.fetchall()

    def get_channel_stats(self):
        """Get channel statistics for reporting"""
        cursor = self.db.cursor()
        
        cursor.execute('''
            SELECT 
                c.name,
                c.subscriber_count,
                AVG(v.views) as avg_views,
                MAX(v.views) as max_views,
                COUNT(v.id) as video_count
            FROM channels c
            LEFT JOIN videos v ON c.id = v.channel_id
            WHERE v.published_date >= datetime('now', '-30 days')
            GROUP BY c.id
            ORDER BY avg_views DESC
        ''')
        
        return cursor.fetchall()

    def close(self):
        """Close the database connection"""
        if self.db:
            self.db.close() 