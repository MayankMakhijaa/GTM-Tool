import sys
import duckduckgo_search

def test_google():
    try:
        dd = duckduckgo_search.DDGS()
        res = dd.text('site:linkedin.com/in "VP Sales" Bengaluru', backend='google')
        print(f"Results type: {type(res)}, count: {len(res) if res else 0}")
        if res:
            print(f"First item: {res[0]}")
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")

if __name__ == '__main__':
    test_google()

