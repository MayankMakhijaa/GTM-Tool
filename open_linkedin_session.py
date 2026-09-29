import os
import time
from playwright.sync_api import sync_playwright

BROWSER_PROFILE_DIR = os.path.join(os.getcwd(), "browser_profile")

def open_session():
    print("Launching Chromium to allow manual logout...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.linkedin.com/")
        print("Browser opened. Please manually log out of LinkedIn in the opened window.")
        print("Waiting for you to log out... Close the browser window when done.")
        
        while not context.pages[0].is_closed():
            try:
                page.wait_for_timeout(1000)
            except Exception:
                break
        print("Browser closed.")

if __name__ == "__main__":
    open_session()
