import urllib.request
import urllib.parse
import re
import json

def test_public_serp(query):
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
            
            # Pattern matches link elements in DuckDuckGo HTML
            matches = re.findall(r'<a class="result__snippet"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            results = []
            for href, snippet in matches:
                clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                # extract real url from uddg parameter
                m = re.search(r'uddg=([^&]+)', href)
                real_url = urllib.parse.unquote(m.group(1)) if m else href
                results.append({
                    "url": real_url,
                    "snippet": clean_snippet
                })
            return results
    except Exception as e:
        return [{"error": str(e)}]

if __name__ == "__main__":
    queries = [
        'site:linkedin.com/in "VP Sales" "B2B SaaS" India',
        'site:linkedin.com/in "Head of Marketing" Bengaluru SaaS',
        '"VP Sales" SaaS India company leadership team'
    ]
    for q in queries:
        print(f"--- QUERY: {q} ---")
        items = test_public_serp(q)
        print(f"Found {len(items)} results")
        for idx, it in enumerate(items[:3], 1):
            print(f"  [{idx}] URL: {it.get('url')}")
            print(f"      Snippet: {it.get('snippet', '')[:120]}")

