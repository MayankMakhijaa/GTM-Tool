import duckduckgo_search

def test_ddg():
    print("--- Testing Native DuckDuckGo via duckduckgo_search ---")
    try:
        dd = duckduckgo_search.DDGS()
        # Test default/html/lite backend
        results = dd.text('site:linkedin.com/in "VP Sales" Bengaluru', max_results=5)
        print(f"Results type: {type(results)}, Count: {len(results) if results else 0}")
        if results:
            print(f"Sample 1: {results[0]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_ddg()

