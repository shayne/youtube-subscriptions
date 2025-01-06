from flask import Flask, jsonify, send_file
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def get_db():
    try:
        conn = sqlite3.connect('youtube.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        app.logger.error(f"Database connection error: {e}")
        raise

def check_db_initialized():
    if not os.path.exists('youtube.db'):
        return False, "Database file not found. Please run init_db.py first."
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Check if required tables exist
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
    # Use YouTube's highest quality thumbnail
    return f'https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg'

@app.route('/')
def serve_app():
    return send_file('index.html')

@app.route('/api/videos')
def get_videos():
    try:
        # Check if database is properly initialized
        is_initialized, error_message = check_db_initialized()
        if not is_initialized:
            return jsonify({
                "error": "Database not initialized", 
                "details": error_message
            }), 500

        db = get_db()
        cursor = db.cursor()
        
        # Join videos with channels to get all necessary data
        cursor.execute('''
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
                CASE 
                    WHEN c.subscriber_count > 0 AND c.average_views > 0 THEN (
                        (v.views * 1.0 / NULLIF(c.average_views, 0)) * 0.6 +  -- Performance vs channel average (60%)
                        (v.views * 1.0 / NULLIF(c.subscriber_count, 0)) * 0.4   -- Reach relative to subscriber base (40%)
                    )
                    ELSE 0 
                END as performance_score
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            ORDER BY performance_score DESC, v.published_date DESC
        ''')
        
        # Fetch all rows before processing
        rows = cursor.fetchall()
        
        # Convert rows to list of dicts
        videos = []
        for row in rows:
            video = dict(row)
            # Ensure published_date is in ISO format
            if video['published_date']:
                try:
                    # Parse the date and convert to ISO format
                    date = datetime.fromisoformat(video['published_date'].replace('Z', '+00:00'))
                    video['published_date'] = date.isoformat()
                except (ValueError, AttributeError) as e:
                    app.logger.error(f"Invalid date format for video {video['id']}: {video['published_date']} - {str(e)}")
                    continue
            
            # Ensure we have a valid thumbnail URL
            video['thumbnail'] = get_thumbnail_url(video['id'], video['thumbnail'])
            
            # Structure the channel data as a nested object
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
            
            # Log the first video's data for debugging
            if len(videos) == 1:
                app.logger.info(f"First video channel data: {video['channel']}")
                app.logger.info(f"First video subscriber count: {video['channel']['subscriber_count']}")
                app.logger.info(f"First video views: {video['views']}")
                app.logger.info(f"First video average views: {video['channel']['average_views']}")
                app.logger.info(f"First video performance score: {video['performance_score']}")
        
        app.logger.info(f"Found {len(videos)} videos")
        if len(videos) > 0:
            app.logger.info(f"Sample video: {videos[0]}")
            app.logger.info(f"Sample channel data: {videos[0]['channel']}")
            app.logger.info(f"Sample video views: {videos[0]['views']}")
            app.logger.info(f"Sample channel average views: {videos[0]['channel']['average_views']}")
            app.logger.info(f"Sample performance score: {videos[0]['performance_score']}")
            app.logger.info(f"Date range: {videos[-1]['published_date']} to {videos[0]['published_date']}")
        
        db.close()
        app.logger.info("Returning JSON response")
        return jsonify(videos)

    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        app.logger.error(f"Server error: {e}")
        return jsonify({"error": "Server error", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 