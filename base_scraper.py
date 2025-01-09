from playwright.sync_api import sync_playwright
import time
import os
import shutil
import tempfile
from pathlib import Path
import atexit
import signal

class BaseScraper:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.chrome_profile_dir = Path("chrome_profile")
        self.playwright = None
        # Register cleanup on exit
        atexit.register(self.cleanup)

    def setup(self):
        """Initialize browser with a persistent Chrome profile"""
        # Create profile directory if it doesn't exist
        self.chrome_profile_dir.mkdir(exist_ok=True)
        print(f"Using Chrome profile at: {self.chrome_profile_dir.absolute()}")

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.chrome_profile_dir),
            channel="chrome",  # Use installed Chrome instead of Chromium
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-web-security',
                '--no-first-run',
                '--no-default-browser-check',
                '--password-store=basic'
            ]
        )
        self.page = self.browser.new_page()
    
    def is_logged_in(self):
        """Check if we're already logged into YouTube"""
        try:
            print("Checking YouTube login status...")
            # First try to go to YouTube homepage
            self.page.goto('https://www.youtube.com')
            self.wait_for_page_load(2)
            
            # Look for sign-in button which indicates we're not logged in
            sign_in_button = self.page.query_selector('a[aria-label="Sign in"]')
            if sign_in_button:
                print("Found sign-in button - not logged in")
                return False
            
            # Try accessing subscriptions page
            print("Checking subscriptions access...")
            self.page.goto('https://www.youtube.com/feed/subscriptions')
            self.wait_for_page_load(2)
            
            # Check if we got redirected to login page
            if 'accounts.google.com' in self.page.url:
                print("Redirected to login page - not logged in")
                return False
            
            # Check if we can see subscription content
            feed = self.page.query_selector('#contents')
            if not feed:
                print("No subscription feed found - not logged in")
                return False
            
            print("Successfully verified login!")
            return True
            
        except Exception as e:
            print(f"Error checking login status: {e}")
            return False

    def check_login(self):
        """Prompt for manual login only if needed"""
        if self.is_logged_in():
            return True
            
        print("\nPlease log in to YouTube in the browser window.")
        print("After logging in, press Enter to continue...")
        input()
        
        # Verify login was successful
        for _ in range(3):  # Try up to 3 times
            if self.is_logged_in():
                return True
            print("Login verification failed, waiting a bit longer...")
            self.wait_for_page_load(2)
        
        return False

    def wait_for_page_load(self, seconds=2):
        """Wait for page to load"""
        time.sleep(seconds)

    def scroll_page(self, amount='window.innerHeight'):
        """Scroll the page by specified amount"""
        try:
            # First verify the page is still in a good state
            self.page.wait_for_load_state('networkidle', timeout=5000)
            
            # Scroll to bottom
            self.page.evaluate('''() => {
                window.scrollTo(0, document.documentElement.scrollHeight);
                return document.documentElement.scrollHeight;
            }''')
            
            # Wait for new content
            self.wait_for_page_load(2)
            
            # Verify page is still responsive
            self.page.wait_for_selector('#contents', timeout=5000)
            
        except Exception as e:
            print(f"Warning: Scroll failed, retrying... ({str(e)})")
            # Give the page a moment to recover
            self.wait_for_page_load(3)
            try:
                # Try one more time with a smaller scroll
                self.page.evaluate('window.scrollBy(0, window.innerHeight)')
                self.wait_for_page_load(2)
            except:
                print("Scroll retry failed, continuing anyway...")

    def cleanup(self):
        """Clean up resources"""
        print("\nCleaning up...")
        try:
            # Set a very short timeout for closing operations
            if hasattr(self, 'page') and self.page:
                try:
                    self.page.close(timeout=1000)
                except:
                    pass
            
            if hasattr(self, 'context') and self.context:
                try:
                    self.context.close(timeout=1000)
                except:
                    pass
                
            if hasattr(self, 'browser') and self.browser:
                try:
                    self.browser.close(timeout=1000)
                except:
                    pass
                    
            if hasattr(self, 'playwright') and self.playwright:
                try:
                    self.playwright.stop()
                except:
                    pass
        except:
            # If anything fails, try to force kill browser
            import psutil
            import os
            try:
                current_process = psutil.Process(os.getpid())
                children = current_process.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except:
                        pass
            except:
                pass
        print("Cleanup complete")

    def run(self):
        """Run the scraper with proper setup and cleanup"""
        def handle_interrupt(signum, frame):
            print("\nInterrupt received, cleaning up...")
            self.cleanup()
            import sys
            sys.exit(0)
            
        # Set up interrupt handler
        signal.signal(signal.SIGINT, handle_interrupt)
        
        try:
            self.setup()
            self.scrape()
        except KeyboardInterrupt:
            print("\nInterrupt received, cleaning up...")
        except Exception as e:
            print(f"\nError during scraping: {e}")
        finally:
            self.cleanup()

    def scrape(self):
        """Override this method in child classes to implement specific scraping logic"""
        raise NotImplementedError("Subclasses must implement scrape()") 