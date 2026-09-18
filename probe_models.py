"""
Quick model probe: check which models are available and quota status.
No grounding tool - just a trivial text call.
"""
import os, sys
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Based on the list: these are the non-deprecated models that exist
CANDIDATES = [
    "models/gemini-3.5-flash-lite",
    "models/gemini-2.5-flash-lite",
    "models/gemini-3.5-flash",
    "models/gemini-3.6-flash",
    "models/gemini-3.1-flash-lite",
]

print("Testing plain generate_content (no grounding) to find quota-available model...")
for model_id in CANDIDATES:
    try:
        res = client.models.generate_content(
            model=model_id,
            contents="Say the word: hello",
            config=types.GenerateContentConfig(temperature=0.0)
        )
        text = (res.text or "").strip()
        print(f"PASS: {model_id} -> '{text[:60]}'")
        break
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print(f"QUOTA: {model_id} -> 429 quota")
        elif "404" in err or "NOT_FOUND" in err:
            print(f"404:   {model_id} -> not found/deprecated")
        else:
            print(f"ERROR: {model_id} -> {err[:100]}")
