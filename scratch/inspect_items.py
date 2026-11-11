import os
import sys
import json
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.openserp_service import OpenSerpDiscoveryService

def inspect_google_and_bing():
    q = urllib.parse.quote_plus('site:linkedin.com/in "VP Sales" "B2B SaaS" Bengaluru')
    
    print("--- Inspecting Google OpenSERP Raw Items ---")
    url_g = f"http://127.0.0.1:7000/google/search?text={q}&limit=8"
    req_g = urllib.request.Request(url_g, headers={"User-Agent": "FameWeb-Test/1.0"})
    with urllib.request.urlopen(req_g) as resp:
        data_g = json.loads(resp.read().decode())
        items_g = data_g.get("results") or []
        for it in items_g:
            parsed = OpenSerpDiscoveryService.parse_candidate_evidence(it, {"id": "q1", "title": "VP Sales"})
            print(f"URL: {it.get('url')[:60]}... | Parsed: {bool(parsed)} | Title: {it.get('title')[:40]}")

    print("\n--- Inspecting Bing OpenSERP Raw Items ---")
    url_b = f"http://127.0.0.1:7000/bing/search?text={q}&limit=8"
    req_b = urllib.request.Request(url_b, headers={"User-Agent": "FameWeb-Test/1.0"})
    with urllib.request.urlopen(req_b) as resp:
        data_b = json.loads(resp.read().decode())
        items_b = data_b.get("results") or []
        for it in items_b:
            parsed = OpenSerpDiscoveryService.parse_candidate_evidence(it, {"id": "q1", "title": "VP Sales"})
            print(f"URL: {it.get('url')[:60]}... | Parsed: {bool(parsed)} | Title: {it.get('title')[:40]}")

if __name__ == "__main__":
    inspect_google_and_bing()

