import urllib.request
import urllib.parse

url = 'http://127.0.0.1:7000/yandex/search?text=' + urllib.parse.quote_plus('site:linkedin.com/in "VP Sales"') + '&limit=5'
print("Querying:", url)
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        print("Status:", resp.status)
        print("Response:", resp.read()[:200])
except urllib.error.HTTPError as he:
    print(f"HTTPError: {he.code} - {he.read()[:200]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

