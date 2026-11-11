import json
import urllib.request
import urllib.parse

q = urllib.parse.quote_plus('site:linkedin.com/in "VP Sales" Bengaluru')
url = f"http://127.0.0.1:7000/duckduckgo/search?text={q}&limit=5"
print(f"Testing OpenSERP DuckDuckGo: {url}")
try:
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        results = data.get("results") or []
        print(f"Status: {resp.status}, Count: {len(results)}")
        if results:
            print("Sample:", results[0])
except Exception as e:
    print(f"Error: {e}")

