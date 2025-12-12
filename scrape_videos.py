from base_scraper import BaseScraper
from db_schema import YouTubeDB
from datetime import datetime, timedelta
import re
import argparse
import json
from urllib import request

class VideoScraper(BaseScraper):
    def __init__(self, debug=False):
        super().__init__(debug)
        self.db = YouTubeDB()
        self.videos = []

    def resolve_channel_using_oembed(self, video_id):
        """Fallback: hit YouTube oEmbed to recover channel info when the feed omits it (e.g., collab videos)."""
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        try:
            with request.urlopen(url, timeout=10) as resp:
                data = json.load(resp)
        except Exception:
            return None, None, None

        author_url = data.get("author_url")
        author_name = data.get("author_name")
        channel_id = None
        if author_url:
            handle_match = re.search(r'/@([A-Za-z0-9_-]+)', author_url)
            id_match = re.search(r'/channel/([A-Za-z0-9_-]+)', author_url)
            if id_match:
                channel_id = id_match.group(1)
            elif handle_match:
                channel_id = handle_match.group(1)
        return channel_id, author_url, author_name

    def ensure_channel_record(self, channel_id, channel_name=None, channel_url=None):
        """Make sure the channel exists in DB before inserting videos."""
        cursor = self.db.db.cursor()
        cursor.execute('SELECT id FROM channels WHERE id = ?', (channel_id,))
        if cursor.fetchone():
            return
        cursor.execute('''
            INSERT INTO channels (id, name, url)
            VALUES (?, ?, ?)
        ''', (
            channel_id,
            channel_name or '',
            channel_url or f'https://www.youtube.com/channel/{channel_id}' if channel_id else ''
        ))
        self.db.db.commit()

    def parse_view_count(self, view_count_text):
        """Convert view count text like '3.2K views', '15K views', '3M views' into numbers."""
        if not view_count_text:
            return 0
        
        # Remove 'views' and any commas, then strip whitespace
        count = view_count_text.lower().replace('views', '').replace(',', '').strip()
        
        try:
            if 'k' in count:
                # Handle thousands (e.g., '3.2K', '15K')
                number = float(count.replace('k', '')) * 1000
            elif 'm' in count:
                # Handle millions (e.g., '3M', '3.4M')
                number = float(count.replace('m', '')) * 1000000
            else:
                # Handle regular numbers (e.g., '492')
                number = float(count)
            return int(number)
        except (ValueError, TypeError):
            print(f"Could not parse view count: {view_count_text}")
            return 0

    def parse_date(self, date_text):
        """Parse date from relative text like '1 month ago'"""
        if not date_text:
            raise ValueError("No date text provided")
        
        # Clean up the text
        text = date_text.lower().replace('streamed', '').strip()
        
        # Handle "just now", "moments ago", etc.
        if text in ['just now', 'moments ago']:
            return datetime.now().isoformat()
            
        # Handle "X minutes ago"
        if 'minute' in text:
            match = re.search(r'(\d+)\s*minute', text)
            if match:
                minutes = int(match.group(1))
                return (datetime.now() - timedelta(minutes=minutes)).isoformat()
        
        # Extract number and unit from relative date
        match = re.match(r'^(\d+)\s+(hour|day|week|month|year)s?\s+ago$', text)
        if not match:
            raise ValueError(f"Could not parse relative date format: '{date_text}'")
        
        number, unit = match.groups()
        number = int(number)
        
        now = datetime.now()
        
        if unit == 'hour':
            return (now - timedelta(hours=number)).isoformat()
        elif unit == 'day':
            return (now - timedelta(days=number)).isoformat()
        elif unit == 'week':
            return (now - timedelta(days=number * 7)).isoformat()
        elif unit == 'month':
            if number == 1:
                # Keep videos that show as "1 month ago"
                return (now - timedelta(days=29)).isoformat()
            else:
                # Multiple months old - definitely too old
                raise ValueError(f"Video too old: {number} months ago")
        elif unit == 'year':
            raise ValueError(f"Video too old: {number} years ago")
        else:
            raise ValueError(f"Unknown time unit in '{date_text}'")

    def scrape(self, days=30):
        """Fetch recent videos from subscriptions"""
        print("\nScanning YouTube subscriptions feed...")
        self.page.goto('https://www.youtube.com/feed/subscriptions')
        self.wait_for_page_load()
        
        # Calculate cutoff date - anything older than 30 days should be trimmed
        cutoff_date = datetime.now() - timedelta(days=30)
        
        # Clean up old videos - anything that's now too old to show up in feed
        cursor = self.db.db.cursor()
        cursor.execute('DELETE FROM videos WHERE published_date < ?', (cutoff_date.isoformat(),))
        trimmed_count = cursor.rowcount
        self.db.db.commit()
        
        processed_video_ids = set()
        old_videos_count = 0
        max_old_videos = 3  # Stop after finding this many old videos
        total_new = 0
        total_updated = 0
        
        # Try different selectors for video elements
        selectors = [
            'ytd-rich-item-renderer:not([is-slim-media])',
            'ytd-rich-grid-media',
            'ytd-grid-video-renderer',
            '#contents > ytd-rich-item-renderer'
        ]
        
        last_height = 0
        no_new_content_count = 0
        max_no_new_content = 3
        
        def update_status(scroll_num, status_line, details="", extra=""):
            """Print a 3-line rolling status update"""
            # Move cursor up 3 lines and clear them
            print('\033[2K\033[1G', end='')  # Clear line and move to start
            print('\033[A' * 3, end='')      # Move up 3 lines
            print(f"Scroll {scroll_num}/20: {status_line}")
            print(details if details else "")
            print(extra if extra else "")
        
        # Make room for status lines once at the start
        print("\n\n")  # Two newlines to make room for 3 lines total
        
        for i in range(20):  # Max scrolls
            update_status(
                i + 1,
                "Loading videos...",
                "Processing latest videos",
                f"Found {len(processed_video_ids)} videos so far"
            )
            
            try:
                # Extract all video information in one JavaScript call
                videos_info = self.page.evaluate(r"""() => {
                    const selectors = [
                        'ytd-rich-item-renderer:not([is-slim-media])',
                        'ytd-rich-grid-media',
                        'ytd-grid-video-renderer',
                        '#contents > ytd-rich-item-renderer'
                    ];
                    let elements = [];

                    // Find first selector that returns elements
                    for (const selector of selectors) {
                        elements = Array.from(document.querySelectorAll(selector));
                        if (elements.length > 0) break;
                    }

                    // Extract info from each element
                    return elements.map(element => {
                        // Title - updated selector for new YouTube structure
                        const titleEl = element.querySelector('h3 a') ||
                                      element.querySelector('a#video-title-link') ||
                                      element.querySelector('#video-title');

                        // Channel - updated to find channel link in new structure
                        const channelEl = element.querySelector('a.yt-core-attributed-string__link') ||
                                        element.querySelector('[href*="/@"]') ||
                                        element.querySelector('[href*="/channel/"]');

                        // Filter out video links from channel links
                        const isChannelLink = channelEl && !channelEl.href.includes('/watch?v=');
                        const finalChannelEl = isChannelLink ? channelEl : null;

                        // Metadata - look for spans in the metadata area
                        const metadataSpans = element.querySelectorAll('yt-lockup-metadata-view-model span');
                        const channelTextFromMetadata = element.querySelector('yt-content-metadata-view-model span')?.textContent?.trim() || null;

                        // Thumbnail
                        const thumbnail = element.querySelector('img.yt-core-image--loaded') ||
                                        element.querySelector('yt-image img');

                        // Duration - updated selector for new YouTube structure
                        const durationEl = element.querySelector('badge-shape.yt-badge-shape div.yt-badge-shape__text') ||
                                         element.querySelector('div.yt-badge-shape__text') ||
                                         element.querySelector('yt-thumbnail-overlay-time-status-view-model span') ||
                                         element.querySelector('ytd-thumbnail-overlay-time-status-renderer span');

                        // Ensure URLs are absolute
                        const absolutize = (href) => {
                            if (!href) return null;
                            if (href.startsWith('http')) return href;
                            return new URL(href, 'https://www.youtube.com').href;
                        };
                        const videoUrl = titleEl ? absolutize(titleEl.getAttribute('href') || titleEl.href) : null;
                        const channelUrl = finalChannelEl ? absolutize(finalChannelEl.getAttribute('href') || finalChannelEl.href) : null;

                        // Parse metadata for views and publish date
                        let publishDate = null;
                        let views = 0;

                        metadataSpans.forEach(span => {
                            const text = span.textContent.trim();
                            if (text.includes('views')) {
                                views = text;
                            } else if (text.includes('ago') || text.includes('hour') || text.includes('day') ||
                                     text.includes('week') || text.includes('month') || text.includes('year')) {
                                publishDate = text;
                            }
                        });

                        // Get channel ID from URL (prefer handle over channel ID)
                        let channelId = null;
                        if (channelUrl) {
                            // First try to get handle
                            const handleMatch = channelUrl.match(/@([\w-]+)/);
                            if (handleMatch) {
                                channelId = handleMatch[1];
                            } else {
                                // Fallback to channel ID if no handle
                                const channelMatch = channelUrl.match(/channel\/([\w-]+)/);
                                if (channelMatch) {
                                    channelId = channelMatch[1];
                                }
                            }
                        }

                        return {
                            title: titleEl ? titleEl.textContent.trim() : null,
                            url: videoUrl,
                            channelName: finalChannelEl ? finalChannelEl.textContent.trim() : null,
                            channelUrl: channelUrl,
                            channelId: channelId,
                            channelText: channelTextFromMetadata,
                            views: views,
                            publishDate: publishDate,
                            thumbnailUrl: thumbnail ? thumbnail.src : null,
                            duration: durationEl ? durationEl.textContent.trim() : null
                        };
                    });
                }""")
                
                if not videos_info:
                    no_new_content_count += 1
                    if no_new_content_count >= max_no_new_content:
                        update_status(i + 1, "No new content found", "Finishing up...", f"Found {len(processed_video_ids)} videos total")
                        break
                    if i < 5:
                        self.wait_for_page_load(2)
                        continue
                    else:
                        break
                
                # Process videos in smaller batches
                batch_size = 10
                new_in_this_scroll = 0
                updated_in_this_scroll = 0
                
                for j in range(0, len(videos_info), batch_size):
                    batch = videos_info[j:j+batch_size]
                    
                    for info in batch:
                        try:
                            if not info['title'] or not info['url']:
                                continue
                                
                            video_info = {
                                'title': info['title'],
                                'url': info['url'],
                                'channel_name': info['channelName'] or info.get('channelText'),
                                'channel_url': info['channelUrl'],
                                'channel_id': info['channelId'],
                                'views': self.parse_view_count(info['views']),
                                'thumbnail': info['thumbnailUrl'],
                                'duration': info.get('duration')
                            }
                            
                            # Parse publish date with error handling
                            try:
                                video_info['publish_date'] = self.parse_date(info['publishDate']) if info['publishDate'] else None
                            except ValueError as e:
                                if "too old" in str(e):
                                    # Expected error for old videos
                                    old_videos_count += 1
                                    if old_videos_count >= max_old_videos:
                                        update_status(i + 1, "Reached older content", "Finishing up...", f"Found {len(processed_video_ids)} videos total")
                                        return
                                    continue
                                else:
                                    # Skip videos with unparseable dates without logging
                                    continue
                            
                            # Skip if no valid publish date
                            if not video_info['publish_date']:
                                continue
                            
                            video_id_match = re.search(r'v=([\w-]+)', video_info['url'])
                            if not video_id_match:
                                continue
                            
                            video_id = video_id_match.group(1)
                            if video_id in processed_video_ids:
                                continue

                            # If channel info missing (common with collaboration cards), hit oEmbed to recover it
                            if not video_info['channel_id']:
                                resolved_id, resolved_url, resolved_name = self.resolve_channel_using_oembed(video_id)
                                if resolved_id:
                                    video_info['channel_id'] = resolved_id
                                if resolved_url and not video_info.get('channel_url'):
                                    video_info['channel_url'] = resolved_url
                                if resolved_name and not video_info.get('channel_name'):
                                    video_info['channel_name'] = resolved_name
                            
                            # Still missing channel? skip to avoid DB FK issues
                            if not video_info['channel_id']:
                                continue
                            
                            processed_video_ids.add(video_id)
                            
                            if video_info['publish_date']:
                                try:
                                    publish_date = datetime.fromisoformat(video_info['publish_date'])
                                    if publish_date < cutoff_date:
                                        old_videos_count += 1
                                        if old_videos_count >= max_old_videos:
                                            update_status(i + 1, "Reached content older than 30 days", "Finishing up...", f"Found {len(processed_video_ids)} videos total")
                                            return
                                        continue
                                except ValueError:
                                    continue
                            
                            cursor = self.db.db.cursor()
                            cursor.execute('SELECT id FROM videos WHERE id = ?', (video_id,))
                            existing_video = cursor.fetchone()

                            # Ensure channel row exists before upserting the video
                            self.ensure_channel_record(
                                video_info['channel_id'],
                                video_info.get('channel_name'),
                                video_info.get('channel_url')
                            )
                            
                            if existing_video:
                                # Update existing video
                                cursor.execute('''
                                    UPDATE videos 
                                    SET title = ?, url = ?, thumbnail = ?, views = ?, published_date = ?, duration = ?
                                    WHERE id = ?
                                ''', (
                                    video_info['title'],
                                    video_info['url'],
                                    video_info['thumbnail'],
                                    video_info['views'],
                                    video_info['publish_date'],
                                    video_info.get('duration'),
                                    video_id
                                ))
                                self.db.db.commit()  # Commit the update
                                updated_in_this_scroll += 1
                                total_updated += 1
                            else:
                                # Insert new video using a simplified insert to avoid double counting
                                cursor.execute('''
                                    INSERT INTO videos 
                                    (id, channel_id, title, url, thumbnail, views, published_date, duration)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    video_id,
                                    video_info['channel_id'],
                                    video_info['title'],
                                    video_info['url'],
                                    video_info['thumbnail'],
                                    video_info['views'],
                                    video_info['publish_date'],
                                    video_info.get('duration')
                                ))
                                self.db.db.commit()  # Commit the insert
                                new_in_this_scroll += 1
                                total_new += 1
                            
                            old_videos_count = 0
                            
                            # Update status every few videos
                            if (new_in_this_scroll + updated_in_this_scroll) % 5 == 0:
                                update_status(
                                    i + 1,
                                    f"Processing videos from scroll {i + 1}",
                                    f"Added {new_in_this_scroll} new, Updated {updated_in_this_scroll} existing",
                                    f"Total videos processed: {len(processed_video_ids)}"
                                )
                        
                        except Exception as e:
                            continue
                
                if new_in_this_scroll == 0 and updated_in_this_scroll == 0:
                    no_new_content_count += 1
                    if no_new_content_count >= max_no_new_content:
                        break
                else:
                    no_new_content_count = 0
                
                current_height = self.page.evaluate('document.documentElement.scrollHeight')
                if current_height == last_height:
                    no_new_content_count += 1
                    if no_new_content_count >= max_no_new_content:
                        update_status(i + 1, "Reached end of feed", "Finishing up...", f"Found {len(processed_video_ids)} videos total")
                        break
                
                last_height = current_height
                self.scroll_page()
                
            except Exception as e:
                if i < 5:
                    self.wait_for_page_load(2)
                    continue
                else:
                    break
        
        # Clear the rolling status and print final summary
        print("\033[3A\033[J")  # Move up 3 lines and clear to end of screen
        print(f"\nScan complete! {total_new} new videos added, {total_updated} videos updated, {trimmed_count} videos trimmed")

    def extract_video_info(self, page):
        """Extract video information from the page."""
        try:
            # Get all video elements
            script = """
            Array.from(document.querySelectorAll('ytd-grid-video-renderer')).map(video => {
                const viewCountText = video.querySelector('#metadata-line span:first-child')?.textContent || '';
                const timeText = video.querySelector('#metadata-line span:last-child')?.textContent || '';
                const titleElement = video.querySelector('#video-title');
                
                return {
                    id: video.querySelector('a#thumbnail')?.href?.split('v=')[1]?.split('&')[0] || '',
                    title: titleElement?.textContent?.trim() || '',
                    url: titleElement?.href || '',
                    thumbnail: video.querySelector('img#img')?.src || '',
                    views: viewCountText,
                    published_date: timeText,
                    channel_id: video.querySelector('ytd-channel-name a')?.href?.split('/channel/')[1]?.split('?')[0] || 
                               video.querySelector('ytd-channel-name a')?.href?.split('@')[1]?.split('/')[0] || ''
                };
            });
            """
            
            videos = page.evaluate(script)
            
            # Process each video
            processed_videos = []
            for video in videos:
                if not video['id'] or not video['title']:
                    continue
                    
                # Parse view count
                video['views'] = self.parse_view_count(video['views'])
                
                # Parse date
                video['published_date'] = self.parse_date(video['published_date'])
                
                processed_videos.append(video)
                
            return processed_videos
        except Exception as e:
            print(f"Error extracting video info: {str(e)}")
            return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape YouTube subscription videos')
    parser.add_argument('--debug', action='store_true', help='Run in non-headless mode')
    args = parser.parse_args()
    
    scraper = VideoScraper(debug=args.debug)
    scraper.run()  # Use run() instead of scrape() to ensure proper setup
    
    # Check if we have channel data and generate feed if we do
    db = scraper.db
    cursor = db.db.cursor()
    cursor.execute('SELECT COUNT(*) FROM channels WHERE subscriber_count > 0')
    channel_count = cursor.fetchone()[0]
    
    if channel_count > 0:
        print("\nChannel data found - generating feed...")
        from generate_feed import main as generate_feed
        generate_feed()
    else:
        print("\nNo channel data found. Run scrape_channel_stats.py to collect channel data.") 
