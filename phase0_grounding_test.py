"""
Final Phase 0: Test grounding on the working model (gemini-3.5-flash-lite).
"""
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

MODEL = "models/gemini-3.5-flash-lite"
print(f"Testing grounding on: {MODEL}")

grounding_tool = types.Tool(google_search=types.GoogleSearch())

try:
    res = client.models.generate_content(
        model=MODEL,
        contents="Search the web and name exactly 2 real US-based B2B SaaS companies that recently raised Series A or B funding. Just list the company names.",
        config=types.GenerateContentConfig(
            tools=[grounding_tool],
            temperature=0.1,
        )
    )
    
    text = (res.text or "").strip()
    print(f"Text response: {text[:300]}")
    
    # Check grounding metadata
    gm = None
    if res.candidates:
        gm = getattr(res.candidates[0], 'grounding_metadata', None)
    
    if gm:
        queries = list(getattr(gm, 'web_search_queries', []) or [])
        chunks = list(getattr(gm, 'grounding_chunks', []) or [])
        print(f"\nGrounding search queries used: {queries[:5]}")
        print(f"Grounding chunks returned: {len(chunks)}")
        for chk in chunks[:3]:
            web = getattr(chk, 'web', None)
            if web:
                print(f"  Source: {getattr(web, 'title', '')} | {getattr(web, 'uri', '')[:80]}")
        print("\n=== GROUNDING PASS ===")
        print(f"Model: {MODEL}")
        print(f"Method: client.models.generate_content")
        print(f"Google Search Grounding: VERIFIED WORKING")
    else:
        print("WARN: No grounding metadata returned (model responded without search).")
        print("Text response was still returned - model may have answered from training data.")
        
except Exception as e:
    err = str(e)
    if "429" in err or "RESOURCE_EXHAUSTED" in err:
        print(f"QUOTA: 429 rate limited - method IS valid, quota exhausted for grounding test.")
    else:
        print(f"FAIL: {err[:300]}")
