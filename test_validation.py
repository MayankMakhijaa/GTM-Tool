import os
import sys

sys.path.append(os.path.join(os.getcwd()))
from app.integrations.linkedin.voyager_client import validate_linkedin_connection, create_voyager_client_from_browser, extract_cookies_from_browser

def test_validation():
    profile_dir = os.path.join(os.getcwd(), "browser_profile")
    print(f"Profile dir: {profile_dir}")
    
    jar = extract_cookies_from_browser(profile_dir)
    print("Extracted cookies:")
    if jar:
        for c in jar:
            print(f" - {c.name}: {c.value[:5]}...")
    else:
        print(" - None returned")
        
    client = create_voyager_client_from_browser(profile_dir)
    print(f"Voyager client: {client}")
    
    if client:
        try:
            client.client._fetch_metadata()
            print("Validation successful!")
        except Exception as e:
            print(f"Validation exception: {type(e).__name__} - {e}")
            
    is_valid = validate_linkedin_connection(profile_dir)
    print(f"Final is_valid: {is_valid}")

if __name__ == "__main__":
    test_validation()
