import json
import urllib.request
import urllib.parse

def test_engine(name, endpoint):
    q = urllib.parse.quote_plus('site:linkedin.com/in "VP Sales" Bengaluru')
    url = f"http://127.0.0.1:7000{endpoint}?text={q}&limit=5"
    print(f"\n--- Testing {name} ({url}) ---")
    req = urllib.request.Request(url, headers={"User-Agent": "FameWeb-Test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results") or []
            print(f"Status: {resp.status}, Results count: {len(results)}")
            if results:
                print(f"Sample result title: {results[0].get('title')}")
                print(f"Sample result url: {results[0].get('url')}")
    except Exception as e:
        print(f"Error for {name}: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_engine("Bing", "/bing/search")
    test_engine("Yandex", "/yandex/search")

