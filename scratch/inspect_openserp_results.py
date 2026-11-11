import json
import os

with open('scratch/openserp_validation/raw_bing.json', 'r', encoding='utf-8') as f:
    bing_data = json.load(f)

print("BING STATUS:", bing_data.get('http_status'))
for idx, r in enumerate(bing_data.get('raw_response', {}).get('results', []), 1):
    print(f"[{idx}] Title: {r.get('title')}")
    print(f"    URL:   {r.get('url')}")
    print(f"    Snip:  {r.get('snippet', '')[:120]}...")

with open('scratch/openserp_validation/raw_google.json', 'r', encoding='utf-8') as f:
    google_data = json.load(f)

print("\nGOOGLE STATUS:", google_data.get('http_status'))
for idx, r in enumerate(google_data.get('raw_response', {}).get('results', []), 1):
    print(f"[{idx}] Title: {r.get('title')}")
    print(f"    URL:   {r.get('url')}")
    print(f"    Snip:  {r.get('snippet', '')[:120]}...")

