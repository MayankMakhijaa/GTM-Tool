"""
List all models available to this API key.
"""
import os
from dotenv import load_dotenv
load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
from google import genai
client = genai.Client(api_key=api_key)

print("Available models for this API key:")
try:
    models = client.models.list()
    for m in models:
        name = getattr(m, 'name', '') or getattr(m, 'id', '') or str(m)
        # Only print genai models
        if 'gemini' in str(name).lower() or 'gemini' in str(m).lower():
            print(f"  {name}")
except Exception as e:
    print(f"Error listing models: {e}")
