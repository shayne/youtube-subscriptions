from playwright.sync_api import sync_playwright
import time
import os
import shutil
import tempfile
from pathlib import Path
import atexit

class BaseScraper:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.chrome_profile_dir = Path("chrome_profile")
        self.playwright = None
        # Register cleanup on exit
        atexit.register(self.cleanup)

    def setup_browser(self):
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
        """Close the browser but keep the profile directory"""
        print("\nCleaning up...")
        try:
            if self.page:
                self.page.close()
                self.page = None
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def run(self):
        """Main execution method"""
        try:
            print("\n=== Starting YouTube Scraper ===")
            
            self.setup_browser()
            self.wait_for_page_load()
            
            # Keep trying until successfully logged in or user quits
            while not self.check_login():
                print("\nLogin failed. Press Enter to try again or Ctrl+C to quit...")
                input()
            
            self.scrape()
            
        except KeyboardInterrupt:
            print("\nScript interrupted by user")
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()

    def scrape(self):
        """Override this method in child classes to implement specific scraping logic"""
        raise NotImplementedError("Subclasses must implement scrape()") 