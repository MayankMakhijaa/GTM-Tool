import os
import sys
import time
import json
import urllib.request
import urllib.parse

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.openserp_service import OpenSerpDiscoveryService

QUERIES = [
    {
        "id": "q1",
        "title": "VP Sales",
        "keywords": "B2B SaaS",
        "location": "Bengaluru",
        "raw_query": 'site:linkedin.com/in "VP Sales" "B2B SaaS" Bengaluru'
    },
    {
        "id": "q2",
        "title": "Chief Revenue Officer",
        "keywords": "Cybersecurity",
        "location": "Mumbai",
        "raw_query": 'site:linkedin.com/in "Chief Revenue Officer" Cybersecurity Mumbai'
    },
    {
        "id": "q3",
        "title": "Head of Engineering",
        "keywords": "",
        "location": "",
        "raw_query": 'site:linkedin.com/in "Head of Engineering" "Sell.Do"'
    }
]

def benchmark_openserp_single(q_obj):
    raw_query = q_obj["raw_query"]
    encoded = urllib.parse.quote_plus(raw_query)
    url = f"http://127.0.0.1:7000/google/search?text={encoded}&limit=8"
    req = urllib.request.Request(url, headers={"User-Agent": "FameWeb-Benchmark/1.0"})
    
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            status_code = resp.status
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            items = data.get("results") or []
            return {
                "success": True,
                "status_code": status_code,
                "status": "SUCCESS",
                "latency_ms": latency_ms,
                "raw_count": len(items),
                "items": items,
                "error": None
            }
    except urllib.error.HTTPError as he:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        err_body = he.read().decode("utf-8", errors="ignore")
        return {
            "success": False,
            "status_code": he.code,
            "status": "CAPTCHA_DETECTED" if "captcha" in err_body.lower() or he.code == 429 else f"HTTP_{he.code}",
            "latency_ms": latency_ms,
            "raw_count": 0,
            "items": [],
            "error": err_body[:200]
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        return {
            "success": False,
            "status_code": 0,
            "status": "EXCEPTION",
            "latency_ms": latency_ms,
            "raw_count": 0,
            "items": [],
            "error": str(exc)
        }

def benchmark_ddgs_single(q_obj):
    import duckduckgo_search
    raw_query = q_obj["raw_query"]
    t0 = time.monotonic()
    try:
        dd = duckduckgo_search.DDGS()
        # Use explicit google backend
        items = dd.text(raw_query, backend="google", max_results=8)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        return {
            "success": True,
            "status_code": 200,
            "status": "SUCCESS" if items else "EMPTY_RESPONSE",
            "latency_ms": latency_ms,
            "raw_count": len(items) if items else 0,
            "items": items or [],
            "error": None
        }
    except Exception as exc:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        err_name = type(exc).__name__
        return {
            "success": False,
            "status_code": 0,
            "status": err_name,
            "latency_ms": latency_ms,
            "raw_count": 0,
            "items": [],
            "error": str(exc)
        }

def normalize_openserp_item(item, q_obj):
    return OpenSerpDiscoveryService.parse_candidate_evidence(item, q_obj)

def normalize_ddgs_item(item, q_obj):
    # DDGS returns {"title": ..., "href": ..., "body": ...}
    adapted = {
        "title": item.get("title", ""),
        "url": item.get("href", ""),
        "description": item.get("body", "")
    }
    return OpenSerpDiscoveryService.parse_candidate_evidence(adapted, q_obj)

def main():
    print("=== STARTING STAGE 6.1 BENCHMARK ===")
    results_report = {"openserp": [], "ddgs": []}

    for idx, q in enumerate(QUERIES, 1):
        print(f"\n--- Running Query {idx}: {q['raw_query']} ---")
        
        # Test OpenSERP
        print("Executing OpenSERP Google...")
        os_res = benchmark_openserp_single(q)
        print(f"OpenSERP status: {os_res['status']} ({os_res['latency_ms']}ms), raw items: {os_res['raw_count']}")
        
        # Normalize OpenSERP
        os_cands = []
        for it in os_res["items"]:
            cand = normalize_openserp_item(it, q)
            if cand:
                cand["adapter"] = "OpenSERP-Google"
                os_cands.append(cand)
        os_res["normalized_candidates"] = os_cands
        results_report["openserp"].append(os_res)

        # Conservative pause between adapters
        time.sleep(6.0)

        # Test DDGS Google
        print("Executing DDGS Google...")
        dd_res = benchmark_ddgs_single(q)
        print(f"DDGS status: {dd_res['status']} ({dd_res['latency_ms']}ms), raw items: {dd_res['raw_count']}")
        
        # Normalize DDGS
        dd_cands = []
        for it in dd_res["items"]:
            cand = normalize_ddgs_item(it, q)
            if cand:
                cand["adapter"] = "DDGS-Google"
                dd_cands.append(cand)
        dd_res["normalized_candidates"] = dd_cands
        results_report["ddgs"].append(dd_res)

        # Conservative pause between queries
        if idx < len(QUERIES):
            print("Pacing 8.0s before next query...")
            time.sleep(8.0)

    # Save raw benchmark output to scratch
    with open("scratch/stage6_1_benchmark_raw.json", "w", encoding="utf-8") as f:
        json.dump(results_report, f, indent=2)
    print("\nBenchmark raw results written to scratch/stage6_1_benchmark_raw.json")

if __name__ == "__main__":
    main()
