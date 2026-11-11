import duckduckgo_search

dd = duckduckgo_search.DDGS()
print("--- TEST BACKEND=BING ---")
try:
    print(dd.text('site:linkedin.com/in "VP Sales" Bengaluru', backend='bing', max_results=3))
except Exception as e:
    print(f"Error: {e}")

print("--- TEST BACKEND=LITE ---")
try:
    print(dd.text('site:linkedin.com/in "VP Sales" Bengaluru', backend='lite', max_results=3))
except Exception as e:
    print(f"Error: {e}")

print("--- TEST BACKEND=GOOGLE ---")
try:
    print(dd.text('site:linkedin.com/in "VP Sales" Bengaluru', backend='google', max_results=3))
except Exception as e:
    print(f"Error: {e}")

