import os
import sys

def test_voyager_adapter():
    from playwright.sync_api import sync_playwright
    from requests.cookies import RequestsCookieJar
    
    voyager_path = os.path.join(os.getcwd(), 'Voyager_api', 'open-linkedin-api-main')
    if voyager_path not in sys.path:
        sys.path.append(voyager_path)
    
    from open_linkedin_api.linkedin import Linkedin
    
    profile_dir = os.path.join(os.getcwd(), "browser_profile")
    
    print("Extracting cookies from browser profile...")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True
        )
        cookies = context.cookies("https://www.linkedin.com")
        context.close()
        
    jar = RequestsCookieJar()
    has_li_at = False
    has_jsessionid = False
    for c in cookies:
        if c['name'] == 'li_at':
            jar.set(c['name'], c['value'], domain=c['domain'])
            has_li_at = True
        elif c['name'] == 'JSESSIONID':
            jar.set(c['name'], c['value'], domain=c['domain'])
            has_jsessionid = True
            
    print(f"Has li_at: {has_li_at}, Has JSESSIONID: {has_jsessionid}")
    
    if has_li_at and has_jsessionid:
        print("Initializing Voyager client...")
        client = Linkedin(username="", password="", authenticate=True, cookies=jar)
        print("Voyager client initialized. Testing minimal request...")
        res = client._fetch("/me")
        print("Response status:", res.status_code)
        
if __name__ == "__main__":
    test_voyager_adapter()
