import urllib.request
import urllib.parse
import re
import json

query = 'site:linkedin.com/in "VP Sales" "B2B SaaS" India'
encoded = urllib.parse.quote_plus(query)
url = f'https://html.duckduckgo.com/html/?q={encoded}'
req = urllib.request.Request(
    url,
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)

with urllib.request.urlopen(req, timeout=10) as resp:
    html = resp.read().decode('utf-8')

# Extract each web-result
blocks = re.findall(r'<div class="[^"]*web-result[^"]*">([\s\S]*?)</div>\s*</div>\s*</div>', html)
print(f"Total web-result blocks found: {len(blocks)}")

for i, b in enumerate(blocks[:6], 1):
    url_m = re.search(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', b)
    title_m = re.search(r'<h2 class="result__title">[\s\S]*?<a[^>]*class="result__a"[^>]*>([\s\S]*?)</a>', b)
    snip_m = re.search(r'<a class="result__snippet"[^>]*>([\s\S]*?)</a>', b)
    
    raw_href = url_m.group(1) if url_m else ''
    display_url = re.sub(r'<[^>]+>', '', url_m.group(2)).strip() if url_m else ''
    title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
    snip = re.sub(r'<[^>]+>', '', snip_m.group(1)).strip() if snip_m else ''
    
    uddg_m = re.search(r'uddg=([^&]+)', raw_href)
    real_url = urllib.parse.unquote(uddg_m.group(1)) if uddg_m else raw_href
    
    print(f"\n=== RAW RESULT #{i} ===")
    print(f"Real URL:    {real_url}")
    print(f"Display URL: {display_url}")
    print(f"Title:       {title}")
    print(f"Snippet:     {snip}")

