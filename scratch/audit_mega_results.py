import json
from app.services.openserp_service import OpenSerpDiscoveryService

with open('scratch/mega_benchmark_raw.json', encoding='utf-8') as f:
    data = json.load(f)

for q in data:
    q_idx = q["query_idx"]
    q_txt = q["query"]
    elapsed = q["elapsed_s"]
    meta = q["meta"]
    print(f"\n=======================================================")
    print(f"QUERY {q_idx}: {q_txt} (Latency: {elapsed:.2f}s)")
    print(f"Responded: {meta.get('engines_responded')} | Failed: {meta.get('engines_failed')}")
    print(f"Errors: {meta.get('engine_errors')}")
    print(f"=======================================================")
    
    results = q.get("results", [])
    seen_urls = set()
    for r in results:
        eng = r.get("engine")
        title = r.get("title")
        raw_url = r.get("url")
        snip = r.get("snippet")
        
        parsed = OpenSerpDiscoveryService.parse_candidate_evidence(r, {"title": q_txt})
        
        is_dup = raw_url in seen_urls
        seen_urls.add(raw_url)
        
        print(f"[{eng.upper()}] Title: {title}")
        print(f"  URL: {raw_url} (Dup: {is_dup})")
        print(f"  Snippet: {snip[:110]}...")
        if parsed:
            print(f"  --> Parsed Name: {parsed['name']} | Role: {parsed['role']} | Company: {parsed['company']} | Loc: {parsed['location']}")
            print(f"  --> Flags: {parsed['validation_flags']}")
        else:
            print(f"  --> Parsed: REJECTED / INVALID (Not a valid profile or identity)")
        print()

