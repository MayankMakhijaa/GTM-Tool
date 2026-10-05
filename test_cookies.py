import os
import sys

sys.path.append(os.path.join(os.getcwd()))
from playwright.sync_api import sync_playwright

def test_cookies():
    profile_dir = os.path.join(os.getcwd(), "browser_profile")
    
    with sync_playwright() as p:
        # We'll just launch, goto linkedin, and print ALL cookies
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True
        )
        page = context.pages[0] if context.pages else context.new_page()
        # Just to ensure cookies are populated
        
        all_cookies = context.cookies()
        print(f"Total cookies in context: {len(all_cookies)}")
        for c in all_cookies[:5]:
            print(f" - {c['name']} (domain: {c['domain']})")
            
        url_cookies = context.cookies("https://www.linkedin.com")
        print(f"\nCookies for https://www.linkedin.com: {len(url_cookies)}")
        
        context.close()

if __name__ == "__main__":
    test_cookies()
