import os
import sys
import json

sys.path.append(os.path.join(os.getcwd()))
from app.integrations.linkedin.voyager_client import create_voyager_client_from_browser

def test_voyager_fetch():
    print("Creating Voyager client...")
    client = create_voyager_client_from_browser()
    if not client:
        print("Failed to create client.")
        return

    print("\nFetching metadata (authentication test)...")
    try:
        client.client._fetch_metadata()
        metadata = client.client.metadata
        print("Metadata fetched. Keys:", list(metadata.keys()))
        if "clientApplicationInstance" in metadata:
            app_inst = metadata["clientApplicationInstance"]
            print(json.dumps(app_inst, indent=2)[:500] + "...")
            
    except Exception as e:
        print("Error fetching metadata:", e)
        return
        
    print("\nTrying to get own profile...")
    # Typically, /me returns the current user profile or we can extract the URN from metadata
    # Let's hit a known voyager endpoint for self profile
    try:
        res = client._fetch("/me")
        print("GET /me Status:", res.status_code)
        if res.status_code == 200:
            print("Response:", json.dumps(res.json(), indent=2)[:500])
    except Exception as e:
        print("Error fetching /me:", e)

if __name__ == "__main__":
    test_voyager_fetch()
