import sqlite3
from datetime import datetime
import os
import math
import json
from pathlib import Path
import webbrowser

def get_db():
    try:
        conn = sqlite3.connect('youtube.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        raise

def check_db_initialized():
    if not os.path.exists('youtube.db'):
        return False, "Database file not found. Please run init_db.py first."
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name IN ('videos', 'channels')
        """)
        
        existing_tables = {row[0] for row in cursor.fetchall()}
        required_tables = {'videos', 'channels'}
        
        if not required_tables.issubset(existing_tables):
            missing_tables = required_tables - existing_tables
            return False, f"Missing tables: {', '.join(missing_tables)}. Please run init_db.py first."
        
        return True, None
        
    except sqlite3.Error as e:
        return False, f"Database error: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()

def get_thumbnail_url(video_id, thumbnail=None):
    """Get a valid thumbnail URL, falling back to YouTube's default if none provided."""
    if thumbnail and thumbnail.strip():
        return thumbnail
    return f'https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg'

def get_videos():
    try:
        is_initialized, error_message = check_db_initialized()
        if not is_initialized:
            print(f"Error: {error_message}")
            return []

        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('''
            WITH ChannelStats AS (
                SELECT 
                    channel_id,
                    AVG(views * 1.0 / c.subscriber_count) as avg_view_sub_ratio
                FROM videos v
                JOIN channels c ON v.channel_id = c.id
                WHERE c.subscriber_count > 0
                GROUP BY channel_id
            )
            SELECT 
                v.id,
                v.title,
                v.url,
                v.thumbnail as thumbnail,
                v.views as views,
                v.published_date,
                c.name as channel_name,
                c.subscriber_count,
                c.is_verified,
                c.thumbnail_url as channel_thumbnail,
                c.average_views as channel_average_views,
                cs.avg_view_sub_ratio,
                CASE 
                    WHEN c.subscriber_count > 0 AND c.average_views > 0 THEN (
                        -- Base performance relative to channel average (50-80% weight depending on view/sub ratio)
                        (v.views * 1.0 / NULLIF(c.average_views, 0)) * 
                        (0.5 + 0.3 * (1.0 - MIN(1.0, cs.avg_view_sub_ratio))) +
                        
                        -- Subscriber reach with adaptive weight (20-50% weight depending on view/sub ratio)
                        (v.views * 1.0 / NULLIF(c.subscriber_count, 0)) * 
                        (0.5 * MIN(1.0, cs.avg_view_sub_ratio)) +
                        
                        -- Non-linear bonus based on view-to-sub ratio relative to channel's typical ratio
                        CASE 
                            WHEN (v.views * 1.0 / c.subscriber_count) > cs.avg_view_sub_ratio THEN 
                                LOG(2, ((v.views * 1.0 / c.subscriber_count) / cs.avg_view_sub_ratio) + 1) * 0.8
                            ELSE 
                                LOG(2, ((v.views * 1.0 / c.subscriber_count) / cs.avg_view_sub_ratio) + 1) * 0.4
                        END
                    )
                    ELSE 0 
                END as performance_score
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            JOIN ChannelStats cs ON v.channel_id = cs.channel_id
            ORDER BY performance_score DESC, v.published_date DESC
        ''')
        
        rows = cursor.fetchall()
        videos = []
        
        for row in rows:
            video = dict(row)
            if video['published_date']:
                try:
                    date = datetime.fromisoformat(video['published_date'].replace('Z', '+00:00'))
                    video['published_date'] = date.isoformat()
                except (ValueError, AttributeError) as e:
                    print(f"Invalid date format for video {video['id']}: {video['published_date']} - {str(e)}")
                    continue
            
            video['thumbnail'] = get_thumbnail_url(video['id'], video['thumbnail'])
            
            subscriber_count = video.pop('subscriber_count')
            average_views = video.pop('channel_average_views')
            performance_score = video.pop('performance_score')
            video['channel'] = {
                'name': video.pop('channel_name'),
                'subscriber_count': int(subscriber_count) if subscriber_count is not None else None,
                'is_verified': bool(video.pop('is_verified')),
                'thumbnail': video.pop('channel_thumbnail'),
                'average_views': int(average_views) if average_views is not None else None
            }
            video['performance_score'] = float(performance_score) if performance_score is not None else 0
            videos.append(video)
        
        db.close()
        return videos

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def generate_html(videos):
    # Read the template HTML file
    template_path = Path(__file__).parent / 'static_template.html'
    with open(template_path, 'r') as f:
        template = f.read()
    
    # Insert the video data as a JSON array
    video_data_json = json.dumps(videos)
    html = template.replace('const videoData = VIDEO_DATA_PLACEHOLDER;', f'const videoData = {video_data_json};')
    
    # Write the generated HTML file
    output_path = Path(__file__).parent / 'youtube_feed.html'
    with open(output_path, 'w') as f:
        f.write(html)
    
    # Get absolute file URL
    file_url = f"file://{output_path.resolve()}"
    
    print(f"\nGenerated static HTML file at: {output_path}")
    print(f"Found {len(videos)} videos")
    if videos:
        print(f"Date range: {videos[-1]['published_date']} to {videos[0]['published_date']}")
    print(f"\nOpening in default browser...")
    
    # Open the file in the default browser
    webbrowser.open(file_url)

def main():
    print("Generating static YouTube feed page...")
    videos = get_videos()
    generate_html(videos)

if __name__ == '__main__':
    main() 