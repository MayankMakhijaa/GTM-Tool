import urllib.request
import urllib.parse
import json
import time

base_url = 'http://127.0.0.1:7000'
queries = [
    'site:linkedin.com/in "VP Sales" "B2B SaaS" Bengaluru',
    'site:linkedin.com/in "Chief Revenue Officer" Cybersecurity Mumbai',
    'site:linkedin.com/in "Head of Engineering" "Sell.Do"'
]

results_archive = []

for idx, q_text in enumerate(queries, 1):
    print(f"=== Executing Benchmark Query {idx}: {q_text} ===")
    encoded = urllib.parse.quote_plus(q_text)
    url = f"{base_url}/mega/search?text={encoded}&limit=5&engines=google,bing"
    
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FameWeb-MegaBenchmark/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - t0
            data = json.loads(resp.read().decode('utf-8'))
            meta = data.get('meta', {})
            results = data.get('results', [])
            responded = meta.get('engines_responded', [])
            failed = meta.get('engines_failed', [])
            errors = meta.get('engine_errors', [])
            print(f"Status 200 in {elapsed:.2f}s | Responded: {responded} | Failed: {failed} | Errors: {errors} | Results: {len(results)}")
            results_archive.append({
                'query_idx': idx,
                'query': q_text,
                'elapsed_s': elapsed,
                'meta': meta,
                'results': results
            })
    except Exception as e:
        print(f"Query {idx} failed with error: {e}")
    
    if idx < len(queries):
        print("Sleeping 5.0s for conservative pacing...")
        time.sleep(5.0)

with open('scratch/mega_benchmark_raw.json', 'w', encoding='utf-8') as f:
    json.dump(results_archive, f, indent=2)

print("Benchmark complete. Saved to scratch/mega_benchmark_raw.json")

