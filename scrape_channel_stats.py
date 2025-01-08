from base_scraper import BaseScraper
from db_schema import YouTubeDB
import re
import json

class ChannelStatsScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.db = YouTubeDB()

    def parse_subscriber_count(self, count_text):
        """Parse subscriber count from text like '1.2M subscribers', '500K subscribers', etc."""
        if not count_text:
            print(f"No subscriber count text provided")
            return None
            
        try:
            print(f"Parsing subscriber count from: '{count_text}'")
            # Remove 'subscribers' and any commas, then strip whitespace
            count = count_text.lower().replace('subscribers', '').replace(',', '').strip()
            
            # Handle special cases
            if count.startswith('@'):  # This is a handle, not a count
                print(f"Got channel handle instead of subscriber count: {count}")
                return None
                
            if count == 'no':  # "No subscribers"
                print(f"Channel has no subscribers")
                return 0
            
            # Remove any leading text like "Verified" or channel name
            count = re.sub(r'^.*?(\d)', r'\1', count)
            
            if 'k' in count:
                # Handle thousands (e.g., '500K', '1.2K')
                number = float(count.replace('k', '')) * 1000
            elif 'm' in count:
                # Handle millions (e.g., '1.2M', '24M')
                number = float(count.replace('m', '')) * 1000000
            else:
                # Handle regular numbers (e.g., '500')
                number = float(count)
            
            result = int(number)
            print(f"Successfully parsed subscriber count '{count_text}' -> {result:,}")
            return result
            
        except (ValueError, TypeError) as e:
            print(f"Could not parse subscriber count '{count_text}': {str(e)}")
            return None

    def extract_channel_stats(self):
        """Extract all channel stats from the channels feed page"""
        try:
            print("\nGoing to channels feed page...")
            response = self.page.goto('https://www.youtube.com/feed/channels')
            self.page.wait_for_load_state('networkidle')
            
            # Get the full page source
            page_source = self.page.content()
            
            # Find all channel renderer JSON objects in the source
            channel_data = []
            
            # Find all instances of channel renderer objects
            pattern = r'\{"channelRenderer":.+?(?=,\{"channelRenderer"|$)'
            matches = re.finditer(pattern, page_source, re.DOTALL)
            
            for match in matches:
                try:
                    # Add closing brace if it was cut off by the regex
                    json_str = match.group(0)
                    if not json_str.endswith('}'):
                        json_str += '}'
                    
                    # Parse the JSON object
                    data = json.loads(json_str)
                    if data and 'channelRenderer' in data:
                        channel_data.append(data)
                except json.JSONDecodeError as e:
                    print(f"Error parsing channel JSON at position {match.start()}: {str(e)[:100]}")
                    continue
            
            print(f"\nFound {len(channel_data)} channels")
            
            channel_info = {}
            for data in channel_data:
                try:
                    channel = data['channelRenderer']
                    channel_id = channel.get('channelId')
                    
                    if not channel_id:
                        continue
                    
                    # Get subscriber count from videoCountText
                    subscriber_text = None
                    video_count_text = channel.get('videoCountText', {})
                    if isinstance(video_count_text, dict):
                        if 'simpleText' in video_count_text:
                            subscriber_text = video_count_text['simpleText']
                        elif 'accessibility' in video_count_text:
                            subscriber_text = video_count_text.get('accessibility', {}).get('accessibilityData', {}).get('label', '')
                    
                    # Get channel handle from subscriberCountText or custom URL
                    handle = None
                    subscriber_count_text = channel.get('subscriberCountText', {})
                    if isinstance(subscriber_count_text, dict) and 'simpleText' in subscriber_count_text:
                        handle_text = subscriber_count_text['simpleText']
                        if handle_text.startswith('@'):
                            handle = handle_text[1:]  # Remove @ symbol
                    
                    if not handle:  # Fallback to custom URL
                        custom_url = channel.get('navigationEndpoint', {}).get('browseEndpoint', {}).get('canonicalBaseUrl', '')
                        if custom_url.startswith('@'):
                            handle = custom_url[1:]  # Remove @ symbol
                    
                    # Check for verification badge
                    is_verified = False
                    owner_badges = channel.get('ownerBadges', [])
                    for badge in owner_badges:
                        badge_renderer = badge.get('metadataBadgeRenderer', {})
                        if badge_renderer.get('style') == 'BADGE_STYLE_TYPE_VERIFIED':
                            is_verified = True
                            break
                    
                    # Extract all channel information
                    channel_info[handle] = {
                        'id': handle,  # Use handle as primary ID
                        'name': channel.get('title', {}).get('simpleText', ''),
                        'url': 'https://youtube.com' + channel.get('navigationEndpoint', {}).get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', ''),
                        'description': channel.get('descriptionSnippet', {}).get('runs', [{}])[0].get('text', ''),
                        'subscriber_count': self.parse_subscriber_count(subscriber_text),
                        'thumbnail_url': None,
                        'is_verified': is_verified,
                        'handle': handle,
                        'youtube_id': channel_id  # Store original YouTube ID as a reference
                    }
                    
                    # Get the highest resolution thumbnail
                    thumbnails = channel.get('thumbnail', {}).get('thumbnails', [])
                    if thumbnails:
                        channel_info[handle]['thumbnail_url'] = thumbnails[-1].get('url', '')
                        if channel_info[handle]['thumbnail_url'].startswith('//'):
                            channel_info[handle]['thumbnail_url'] = 'https:' + channel_info[handle]['thumbnail_url']
                    
                    print(f"Found channel {channel_info[handle]['name']} (@{channel_info[handle]['handle']}): {channel_info[handle]['subscriber_count']:,} subscribers {'✓' if is_verified else ''}")
                    
                except Exception as e:
                    print(f"Error processing channel: {e}")
                    continue
            
            return channel_info
            
        except Exception as e:
            print(f"Error extracting channel stats: {e}")
            return {}

    def get_channel_average_views(self, channel_url):
        """Calculate average views from the last 30 videos by visiting the channel page, excluding top and bottom 3 performing videos"""
        try:
            print(f"\nGetting average views from {channel_url}...")
            self.page.goto(channel_url + '/videos')
            self.page.wait_for_load_state('networkidle')
            
            # Scroll a few times to load more videos
            last_height = 0
            for _ in range(3):  # Scroll 3 times to get more videos
                self.page.evaluate('window.scrollTo(0, document.documentElement.scrollHeight)')
                self.page.wait_for_timeout(1000)  # Wait for content to load
                new_height = self.page.evaluate('document.documentElement.scrollHeight')
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Extract video information using JavaScript
            videos_info = self.page.evaluate("""() => {
                const videos = Array.from(document.querySelectorAll('ytd-rich-grid-media, ytd-grid-video-renderer')).slice(0, 30);
                return videos.map(video => {
                    const metadataLine = video.querySelector('#metadata-line');
                    let viewCountText = '';
                    if (metadataLine) {
                        const spans = Array.from(metadataLine.querySelectorAll('span'));
                        for (const span of spans) {
                            if (span.textContent.includes('views')) {
                                viewCountText = span.textContent;
                                break;
                            }
                        }
                    }
                    return { views: viewCountText };
                });
            }""")
            
            if not videos_info:
                print("No videos found on channel page")
                return 0
            
            # Parse view counts
            views = []
            for video in videos_info:
                try:
                    view_count = self.parse_view_count(video['views'])
                    if view_count > 0:
                        views.append(view_count)
                except Exception as e:
                    print(f"Error parsing view count: {e}")
                    continue
            
            if len(views) >= 7:  # Only exclude top/bottom 3 if we have at least 7 videos
                # Sort views in ascending order
                views.sort()
                # Remove bottom 3 and top 3 performing videos
                views = views[3:-3]
                print(f"Excluded top and bottom 3 performing videos from average calculation")
            
            if views:
                average = int(sum(views) / len(views))
                print(f"Calculated average views from {len(views)} videos: {average:,}")
                return average
            
            print("No valid view counts found")
            return 0
            
        except Exception as e:
            print(f"Error getting channel average views: {e}")
            return 0

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

    def update_channel_info(self, channel_id, info):
        """Update channel information in the database"""
        cursor = self.db.db.cursor()
        
        try:
            # Calculate average views from last 10 videos on channel page
            average_views = self.get_channel_average_views(info['url'])
            
            # First check if channel exists
            cursor.execute('SELECT id FROM channels WHERE id = ?', (channel_id,))
            channel_exists = cursor.fetchone() is not None
            
            if channel_exists:
                # Update only specific fields for existing channels
                cursor.execute('''
                    UPDATE channels 
                    SET subscriber_count = ?,
                        is_verified = ?,
                        handle = ?,
                        average_views = ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    info['subscriber_count'],
                    info['is_verified'],
                    info['handle'],
                    average_views,
                    channel_id
                ))
                print(f"Updated channel {info['name']} with {info['subscriber_count']:,} subscribers (avg views: {average_views:,})")
            else:
                # Insert new channel with all fields
                cursor.execute('''
                    INSERT INTO channels 
                    (id, name, url, subscriber_count, description, thumbnail_url, is_verified, handle, average_views, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    channel_id,
                    info['name'],
                    info['url'],
                    info['subscriber_count'],
                    info['description'],
                    info['thumbnail_url'],
                    info['is_verified'],
                    info['handle'],
                    average_views
                ))
                print(f"Inserted new channel {info['name']} with {info['subscriber_count']:,} subscribers (avg views: {average_views:,})")
            
            self.db.db.commit()
            
        except Exception as e:
            print(f"Error updating channel {channel_id}: {e}")
            self.db.db.rollback()

    def scrape(self):
        """Scrape channel information from the subscriptions page"""
        print("\nFetching channel statistics...")
        
        # Get all channel stats from the feed page
        channel_info = self.extract_channel_stats()
        
        if not channel_info:
            print("No channels found on subscriptions page.")
            return
        
        # Update information for all channels found
        updated_count = 0
        for channel_id, info in channel_info.items():
            try:
                subscriber_count = info.get('subscriber_count')
                if subscriber_count is not None:  # Only update if we have a valid subscriber count
                    self.update_channel_info(channel_id, info)
                    print(f"Updated info for {info['name']} (@{info['handle']}): {subscriber_count:,} subscribers")
                    updated_count += 1
                else:
                    print(f"Skipping update for {info['name']} - no valid subscriber count")
            except Exception as e:
                print(f"Error updating channel {channel_id}: {e}")
        
        print(f"\nFinished updating {updated_count} channel statistics!")

if __name__ == "__main__":
    scraper = ChannelStatsScraper()
    scraper.run() 