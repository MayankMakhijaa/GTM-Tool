import urllib.request
import urllib.parse
import re

query = 'site:linkedin.com/in "VP Sales" "B2B SaaS" India'
encoded = urllib.parse.quote_plus(query)
url = f'https://html.duckduckgo.com/html/?q={encoded}'
req = urllib.request.Request(
    url,
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)

with urllib.request.urlopen(req, timeout=10) as resp:
    html = resp.read().decode('utf-8')

print("HTML length:", len(html))
print("First 500 chars:")
print(html[:500])

# Find all links with uddg
links = re.findall(r'<a[^>]+href="([^"]*uddg[^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
print(f"\nTotal uddg links found: {len(links)}")
for idx, (href, text) in enumerate(links[:10], 1):
    m = re.search(r'uddg=([^&]+)', href)
    real_url = urllib.parse.unquote(m.group(1)) if m else href
    clean_text = re.sub(r'<[^>]+>', '', text).strip()
    print(f"[{idx}] Text: {clean_text[:60]} | URL: {real_url}")

