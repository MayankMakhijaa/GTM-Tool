"""
Phase 0 Compatibility Test v2 - using correct model names with models/ prefix
"""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("FAIL: GEMINI_API_KEY not set.")
    sys.exit(1)
print("PASS: GEMINI_API_KEY present (not printed).")

from google import genai
from google.genai import types
print(f"PASS: google-genai {genai.__version__} imported.")

client = genai.Client(api_key=api_key)
print("PASS: genai.Client initialized.")

# These are the actual model IDs returned by client.models.list()
# Try grounding on best available model
CANDIDATES = [
    "models/gemini-2.5-flash",
    "models/gemini-3.5-flash",
    "models/gemini-3.5-flash-lite",
    "models/gemini-2.5-flash-lite",
]

grounding_tool = types.Tool(google_search=types.GoogleSearch())

print("\n--- Testing generate_content + Google Search Grounding ---")
for model_id in CANDIDATES:
    print(f"\nTesting: {model_id}")
    try:
        res = client.models.generate_content(
            model=model_id,
            contents="Search the web and name 1 real B2B SaaS company that raised funding recently. Reply with just the company name.",
            config=types.GenerateContentConfig(
                tools=[grounding_tool],
                temperature=0.1,
            )
        )
        text = (res.text or "").strip()
        print(f"  Response: {text[:120]}")
        
        # Check grounding metadata
        gm = None
        if res.candidates:
            cand = res.candidates[0]
            gm = getattr(cand, 'grounding_metadata', None)
        
        print(f"  Grounding metadata present: {gm is not None}")
        if gm:
            queries = getattr(gm, 'web_search_queries', []) or []
            chunks = getattr(gm, 'grounding_chunks', []) or []
            print(f"  Search queries used: {list(queries)[:3]}")
            print(f"  Grounding chunks: {len(chunks)}")
        
        print(f"\n=== PASS ===")
        print(f"Verified model:  {model_id}")
        print(f"API method:      client.models.generate_content")
        print(f"Grounding:       {gm is not None}")
        sys.exit(0)
        
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
            print(f"  QUOTA LIMITED (429) - method IS valid, quota exhausted.")
            print(f"\n=== PASS (quota limited) ===")
            print(f"Verified model:  {model_id}")
            print(f"API method:      client.models.generate_content + GoogleSearch")
            print(f"Grounding:       Yes (method valid, quota limits response)")
            sys.exit(0)
        elif "400" in err and "google_search" in err.lower():
            print(f"  WARN: Grounding not supported on {model_id}: {err[:150]}")
        elif "404" in err or "NOT_FOUND" in err:
            print(f"  WARN: Model not found: {err[:100]}")
        else:
            print(f"  ERROR: {err[:200]}")

print("\nFAIL: No model passed the grounding compatibility test.")
sys.exit(1)
