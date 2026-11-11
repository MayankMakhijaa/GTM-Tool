import urllib.request
import urllib.parse

query = 'site:linkedin.com/in "VP Sales" "B2B SaaS" India'
encoded = urllib.parse.quote_plus(query)
url = f'https://html.duckduckgo.com/html/?q={encoded}'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
with urllib.request.urlopen(req, timeout=10) as resp:
    html = resp.read().decode('utf-8')

with open('scratch/ddg_sample.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Wrote scratch/ddg_sample.html. Size:', len(html))

