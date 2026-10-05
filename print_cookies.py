import os
import sys

sys.path.append(os.path.join(os.getcwd()))
from playwright.sync_api import sync_playwright

def print_cookies():
    profile_dir = os.path.join(os.getcwd(), "browser_profile")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True
        )
        cookies = context.cookies("https://www.linkedin.com")
        for c in cookies:
            print(f"{c['name']} = {c['value'][:10]}...")
        context.close()

if __name__ == "__main__":
    print_cookies()
