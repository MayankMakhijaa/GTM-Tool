import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

def test_direct_html_ddg():
    url = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({'q': 'site:linkedin.com/in "VP Sales" Bengaluru'}).encode()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://html.duckduckgo.com/"
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            print(f"Status: {resp.status}, Body length: {len(body)}")
            if "anomaly-modal" in body or "captcha" in body.lower():
                print("DDG Captcha/Anomaly detected")
            elif "No  results." in body or "No results" in body:
                print("No results returned by DDG HTML")
            else:
                print("Results present!")
                print("Sample body slice:", body[:500])
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_direct_html_ddg()

