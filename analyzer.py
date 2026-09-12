import os
import json
from typing import List, Dict, Any
from google import genai
from google.genai import types

def analyze_comments(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Use Gemini to analyze a list of structured LinkedIn comments and extract qualified leads deterministically.
    Uses temperature=0.0 and explicit qualification rules to guarantee consistent filtering across runs.
    """
    if not comments:
        return []

    # Separate candidates from obvious low-value items/post-author replies
    evaluated_results: List[Dict[str, Any]] = []
    candidates_to_analyze: List[Dict[str, Any]] = []

    for item in comments:
        name = str(item.get("name", "") or "").strip()
        headline = str(item.get("headline", "") or "").strip()
        comment_text = str(item.get("comment", "") or "").strip()
        is_author_reply = bool(item.get("is_author_reply", False))
        is_candidate = bool(item.get("is_candidate", True))

        if is_author_reply:
            evaluated_results.append({
                "name": name,
                "headline": headline or None,
                "comment": comment_text,
                "lead": False,
                "lead_score": 0,
                "company": None,
                "role": None,
                "business_need": None,
                "intent": None,
                "reason": "Post author response",
                "lead_type": None,
                "email": None,
                "phone": None,
                "profile_url": None
            })
        elif not is_candidate:
            evaluated_results.append({
                "name": name,
                "headline": headline or None,
                "comment": comment_text,
                "lead": False,
                "lead_score": 0,
                "company": None,
                "role": None,
                "business_need": None,
                "intent": None,
                "reason": "Filtered as low-value profile without business buying intent",
                "lead_type": None,
                "email": None,
                "phone": None,
                "profile_url": None
            })
        else:
            candidates_to_analyze.append({
                "name": name,
                "headline": headline or None,
                "comment": comment_text
            })

    if not candidates_to_analyze:
        return evaluated_results

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY not found in environment.")
        for cand in candidates_to_analyze:
            evaluated_results.append({
                **cand,
                "lead": False,
                "lead_score": 0,
                "company": None,
                "role": None,
                "business_need": None,
                "intent": None,
                "reason": "GEMINI_API_KEY missing",
                "lead_type": None,
                "email": None,
                "phone": None,
                "profile_url": None
            })
        return evaluated_results

    try:
        client = genai.Client(api_key=api_key)
        
        # Sort candidates deterministically before invoking Gemini
        sorted_candidates = sorted(
            candidates_to_analyze,
            key=lambda x: (str(x.get("name", "")).lower(), str(x.get("comment", "")).lower())
        )

        input_data = json.dumps(sorted_candidates)
        
        prompt = f"""
You are a deterministic B2B lead qualification system.
Analyze the following structured list of LinkedIn commenter records (containing name, headline, and comment).

DETERMINISTIC QUALIFICATION MATRIX:
1. QUALIFIED LEAD (`lead`: true):
   - Comment explicitly seeks solutions, software, vendor services, demos, pricing, or implementation details.
   - Comment describes an active business challenge, workflow pain point, or implementation project.
   - Commenter role/headline indicates a decision maker, evaluator, or buyer (Founder, CEO, CTO, VP, Director, Lead, Manager, Consultant) AND comment is non-generic.
   - For QUALIFIED leads:
     * `lead_score`: 70 to 100
     * `intent`: "High" or "Medium"
     * `lead_type`: "Decision Maker", "Evaluator", or "Prospect"
     * `business_need`: Concise description of stated or implied business problem
     * `company`: Extract company name ONLY if explicitly identifiable in the headline/comment. Otherwise null.
     * `role`: Extract job title/role ONLY if explicitly identifiable in the headline/comment. Otherwise null.
     * `reason`: Concise justification based on comment/headline text

2. DISQUALIFIED COMMENT (`lead`: false):
   - Generic praise or politeness (e.g. "Great post", "Agreed", "Thanks for sharing", "Awesome").
   - Personal anecdotes without business software/service intent.
   - For DISQUALIFIED comments:
     * `lead_score`: 0 to 39
     * `intent`: "Low" or null
     * `lead_type`: null
     * `business_need`: null
     * `company`: Extract ONLY if present in headline/comment, else null.
     * `role`: Extract ONLY if present in headline/comment, else null.
     * `reason`: "Generic or non-buying comment"

CRITICAL INSTRUCTIONS:
- NEVER guess, invent, or construct an email address or phone number. Return null for email and phone.
- Return null for profile_url.
- Return a JSON array containing analyzed objects for ALL input items in the EXACT SAME ORDER as provided.

Input candidates:
{input_data}
"""

        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                seed=42,
                response_mime_type="application/json",
            ),
        )
        
        result_text = response.text
        if not result_text:
            raise ValueError("Gemini API returned an empty response.")

        analyzed_data = json.loads(result_text)
        if isinstance(analyzed_data, list):
            for i, item in enumerate(analyzed_data):
                if isinstance(item, dict):
                    cand = sorted_candidates[i] if i < len(sorted_candidates) else {}
                    item["name"] = cand.get("name") or item.get("name") or "Unknown"
                    item["headline"] = cand.get("headline") or item.get("headline")
                    item["email"] = item.get("email") or None
                    item["phone"] = item.get("phone") or None
                    item["profile_url"] = None
                    evaluated_results.append(item)

        return evaluated_results
    except Exception as e:
        print(f"Gemini Analysis Error: {str(e)}")
        for cand in candidates_to_analyze:
            evaluated_results.append({
                **cand,
                "lead": False,
                "lead_score": 0,
                "company": None,
                "role": None,
                "business_need": None,
                "intent": None,
                "reason": "Analysis error",
                "lead_type": None,
                "email": None,
                "phone": None,
                "profile_url": None
            })
        return evaluated_results

