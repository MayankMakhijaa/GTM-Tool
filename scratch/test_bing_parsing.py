import os
import sys
import json
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.openserp_service import OpenSerpDiscoveryService

def test_bing_candidate_parsing():
    q = urllib.parse.quote_plus('site:linkedin.com/in "VP Sales" Bengaluru')
    url = f"http://127.0.0.1:7000/bing/search?text={q}&limit=8"
    req = urllib.request.Request(url, headers={"User-Agent": "FameWeb-Test/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        items = data.get("results") or []
        print(f"Bing raw items count: {len(items)}")
        
        parsed_candidates = []
        for it in items:
            cand = OpenSerpDiscoveryService.parse_candidate_evidence(it, {"id": "q1", "title": "VP Sales"})
            if cand:
                parsed_candidates.append(cand)
                
        print(f"Successfully parsed & evidence-grounded: {len(parsed_candidates)}")
        for c in parsed_candidates:
            print(f"  Candidate: {c['name']} | Role: {c['role']} | Company: {c['company']} | Loc: {c['location']} | URL: {c['profile_url']}")

if __name__ == "__main__":
    test_bing_candidate_parsing()
