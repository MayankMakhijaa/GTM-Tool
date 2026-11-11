from ddgs import DDGS

print("--- Testing ddgs==9.16.1 Native DuckDuckGo ---")
try:
    with DDGS() as dd:
        res = dd.text('site:linkedin.com/in "VP Sales" Bengaluru', backend="duckduckgo", max_results=5)
        print(f"ddgs DuckDuckGo backend count: {len(res) if res else 0}")
        if res:
            print(f"Sample: {res[0]}")
except Exception as e:
    print(f"Error: {e}")

