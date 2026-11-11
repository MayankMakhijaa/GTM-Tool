import urllib.request
import urllib.parse
import json
import time
import os
import re

OUTPUT_DIR = r"d:\Programming\FameWebs_Internship\linkedin_lead_generator\scratch\openserp_validation"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ENGINES_TO_TEST = [
    ("duckduckgo", "duck"),
    ("bing", "bing"),
    ("google", "google")
]

TEST_QUERY = 'site:linkedin.com/in "VP Sales" "B2B SaaS" India'

def execute_openserp_test():
    all_engine_results = []
    
    print("=================================================================")
    print("OPENSERP STANDALONE FEASIBILITY TEST (LOCAL HTTP)")
    print("=================================================================\n")

    for engine_name, engine_endpoint in ENGINES_TO_TEST:
        encoded_q = urllib.parse.quote_plus(TEST_QUERY)
        url = f"http://127.0.0.1:7000/{engine_endpoint}/search?text={encoded_q}&limit=5"
        
        print(f"Testing Engine: [{engine_name.upper()}]")
        print(f"GET {url}")
        
        t0 = time.time()
        record = {
            "engine": engine_name,
            "endpoint": engine_endpoint,
            "query": TEST_QUERY,
            "url": url,
            "http_status": None,
            "took_seconds": None,
            "raw_response": None,
            "status_category": "UNKNOWN",
            "results_count": 0,
            "candidates": [],
            "error_message": None
        }

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FameWeb-OpenSERP-Tester/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                elapsed = time.time() - t0
                record["http_status"] = resp.status
                record["took_seconds"] = round(elapsed, 2)
                
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8"))
                record["raw_response"] = data
                
                # Check for meta / errors
                meta = data.get("meta", {})
                engines_failed = meta.get("engines_failed", [])
                
                # In OpenSERP v2: results are under "results" array
                items = data.get("results", [])
                record["results_count"] = len(items)
                
                if engine_name in engines_failed:
                    record["status_category"] = "ENGINE_REPORTED_FAILURE"
                elif len(items) > 0:
                    record["status_category"] = "RESULTS_RETURNED"
                else:
                    record["status_category"] = "EMPTY_OR_NO_RESULTS"

                print(f"   -> HTTP {resp.status} in {record['took_seconds']}s | Items: {len(items)} | Category: {record['status_category']}")

        except urllib.error.HTTPError as he:
            elapsed = time.time() - t0
            record["http_status"] = he.code
            record["took_seconds"] = round(elapsed, 2)
            err_body = he.read().decode("utf-8", errors="ignore")
            try:
                record["raw_response"] = json.loads(err_body)
            except:
                record["raw_response"] = err_body
            
            if he.code in (429, 403):
                record["status_category"] = "RATE_LIMITED_OR_BLOCKED"
            elif he.code == 502:
                record["status_category"] = "UPSTREAM_BLOCKED_OR_FAILED"
            else:
                record["status_category"] = f"HTTP_{he.code}_ERROR"
            record["error_message"] = str(he)
            print(f"   -> HTTP ERROR {he.code} in {record['took_seconds']}s: {err_body[:150]}")

        except Exception as e:
            elapsed = time.time() - t0
            record["took_seconds"] = round(elapsed, 2)
            record["status_category"] = "CONNECTION_EXCEPTION"
            record["error_message"] = str(e)
            print(f"   -> EXCEPTION in {record['took_seconds']}s: {e}")

        # Save individual engine raw response
        with open(os.path.join(OUTPUT_DIR, f"raw_{engine_name}.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)

        all_engine_results.append(record)
        print("-----------------------------------------------------------------")
        time.sleep(2) # Politeness delay between engine tests

    return all_engine_results

if __name__ == "__main__":
    execute_openserp_test()

