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
                    AVG(views * 1.0 / c.subscriber_count) as avg_view_sub_ratio,
                    -- Calculate median views for better outlier handling
                    -- Using approximate median calculation
                    AVG(views) as avg_views,
                    COUNT(*) as video_count
                FROM videos v
                JOIN channels c ON v.channel_id = c.id
                WHERE c.subscriber_count > 0
                GROUP BY channel_id
            ), VideoMetrics AS (
                SELECT
                    v.*,
                    c.name as channel_name,
                    c.subscriber_count,
                    c.is_verified,
                    c.thumbnail_url as channel_thumbnail,
                    c.average_views as channel_average_views,
                    cs.avg_view_sub_ratio,
                    -- Calculate video age in hours
                    (julianday('now') - julianday(v.published_date)) * 24 as video_age_hours,
                    -- Views per hour (velocity metric)
                    CASE 
                        WHEN (julianday('now') - julianday(v.published_date)) * 24 > 0 
                        THEN v.views * 1.0 / ((julianday('now') - julianday(v.published_date)) * 24)
                        ELSE v.views 
                    END as views_per_hour,
                    -- Observed fraction of 48h views, assuming ~60% in first 8h and 95% by 48h
                    CASE
                        WHEN (julianday('now') - julianday(v.published_date)) * 24 <= 0 THEN 0.05
                        WHEN (julianday('now') - julianday(v.published_date)) * 24 <= 8 THEN 
                            MAX(0.05, 0.6 * (((julianday('now') - julianday(v.published_date)) * 24) / 8.0))
                        WHEN (julianday('now') - julianday(v.published_date)) * 24 < 48 THEN 
                            0.6 + 0.35 * ((((julianday('now') - julianday(v.published_date)) * 24) - 8.0) / 40.0)
                        ELSE 0.95
                    END as observed_fraction_48h,
                    -- Predicted 48h views based on the above curve
                    CASE
                        WHEN (julianday('now') - julianday(v.published_date)) * 24 < 48 THEN
                            v.views * 0.95 / NULLIF(
                                CASE
                                    WHEN (julianday('now') - julianday(v.published_date)) * 24 <= 0 THEN 0.05
                                    WHEN (julianday('now') - julianday(v.published_date)) * 24 <= 8 THEN 
                                        MAX(0.05, 0.6 * (((julianday('now') - julianday(v.published_date)) * 24) / 8.0))
                                    WHEN (julianday('now') - julianday(v.published_date)) * 24 < 48 THEN 
                                        0.6 + 0.35 * ((((julianday('now') - julianday(v.published_date)) * 24) - 8.0) / 40.0)
                                END,
                                0.05
                            )
                        ELSE v.views
                    END as predicted_views_48h
                FROM videos v
                JOIN channels c ON v.channel_id = c.id
                JOIN ChannelStats cs ON v.channel_id = cs.channel_id
            )
            SELECT 
                vm.id,
                vm.title,
                vm.url,
                vm.thumbnail as thumbnail,
                vm.views as views,
                vm.published_date,
                vm.duration,
                vm.channel_name,
                vm.subscriber_count,
                vm.is_verified,
                vm.channel_thumbnail,
                vm.channel_average_views,
                vm.avg_view_sub_ratio,
                vm.video_age_hours,
                vm.views_per_hour,
                vm.observed_fraction_48h,
                vm.predicted_views_48h,
                
                -- PERFORMANCE SCORE focused on standout content with early-velocity forecast
                CASE 
                    WHEN vm.subscriber_count > 0 AND vm.channel_average_views > 0 THEN 
                        (
                            -- 1. Base performance relative to channel average (35% weight)
                            (MIN(vm.views * 1.0 / NULLIF(vm.channel_average_views, 0), 5.0) / 5.0) * 0.35 +
                            
                            -- 2. Subscriber engagement rate (25% weight)
                            CASE 
                                WHEN vm.subscriber_count > 0 THEN
                                    MIN(SQRT((vm.views * 1.0 / vm.subscriber_count) * 10), 1.0) * 0.25
                                ELSE 0
                            END +
                            
                            -- 3. Forecasted 48h performance (20% weight)
                            (MIN(vm.predicted_views_48h * 1.0 / NULLIF(vm.channel_average_views, 0), 5.0) / 5.0) * 0.20 +
                            
                            -- 4. Velocity metric (10% weight)
                            CASE
                                WHEN vm.video_age_hours > 1 THEN
                                    MIN(LOG10(1 + (vm.views * 1.0 / NULLIF(vm.video_age_hours, 1))) / 5.0, 1.0) * 0.10
                                ELSE 0.10
                            END +
                            
                            -- 5. Channel size normalization (7% weight)
                            CASE
                                WHEN vm.subscriber_count < 100000 THEN 0.07
                                WHEN vm.subscriber_count < 1000000 THEN 0.05
                                WHEN vm.subscriber_count < 10000000 THEN 0.02
                                ELSE 0
                            END +
                            
                            -- 6. Duration adjustment (3% weight)
                            CASE
                                WHEN vm.duration IS NOT NULL AND vm.duration > 0 THEN
                                    CASE
                                        WHEN vm.duration < 120 THEN 0.01  -- < 2 minutes
                                        WHEN vm.duration < 600 THEN 0.02  -- 2-10 minutes
                                        WHEN vm.duration < 1800 THEN 0.03 -- 10-30 minutes (sweet spot)
                                        WHEN vm.duration < 3600 THEN 0.02 -- 30-60 minutes
                                        ELSE 0.015 -- > 60 minutes
                                    END
                                ELSE 0.015 -- Default if no duration
                            END
                        )
                        
                    ELSE 0 
                END as performance_score,
                
                -- Individual score components for debugging
                CASE WHEN vm.channel_average_views > 0 THEN (vm.views * 1.0 / NULLIF(vm.channel_average_views, 0)) ELSE 0 END as relative_performance,
                CASE WHEN vm.subscriber_count > 0 THEN (vm.views * 1.0 / vm.subscriber_count) ELSE 0 END as subscriber_reach,
                CASE WHEN vm.channel_average_views > 0 THEN (vm.predicted_views_48h * 1.0 / NULLIF(vm.channel_average_views, 0)) ELSE 0 END as forecast_relative_performance,
                CASE WHEN vm.video_age_hours > 1 THEN
                    vm.views * 1.0 / vm.video_age_hours
                ELSE vm.views END as velocity
                
            FROM VideoMetrics vm
            ORDER BY performance_score DESC, vm.published_date DESC
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
            video['duration'] = video.get('duration')  # Keep duration in the video object
            
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
            video['performance_details'] = {
                'relative_performance': float(row['relative_performance']) if row['relative_performance'] is not None else 0,
                'subscriber_reach': float(row['subscriber_reach']) if row['subscriber_reach'] is not None else 0,
                'forecast_relative_performance': float(row['forecast_relative_performance']) if row['forecast_relative_performance'] is not None else 0,
                'velocity': float(row['velocity']) if row['velocity'] is not None else 0,
                'video_age_hours': float(row['video_age_hours']) if row['video_age_hours'] is not None else 0,
                'views_per_hour': float(row['views_per_hour']) if row['views_per_hour'] is not None else 0,
                'observed_fraction_48h': float(row['observed_fraction_48h']) if row['observed_fraction_48h'] is not None else 0,
                'predicted_views_48h': float(row['predicted_views_48h']) if row['predicted_views_48h'] is not None else 0
            }
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
