import os
import json
from typing import List, Dict, Any
from google import genai
from google.genai import types

def analyze_comments(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Use Gemini 3.5 Flash Lite with Google Search Grounding to verify and qualify LinkedIn leads.
    """
    if not comments:
        return []

    evaluated_results: List[Dict[str, Any]] = []
    candidates_to_analyze: List[Dict[str, Any]] = []

    for item in comments:
        name = str(item.get("name", "") or "").strip()
        headline = str(item.get("headline", "") or "").strip()
        comment_text = str(item.get("comment", "") or "").strip()
        is_author_reply = bool(item.get("is_author_reply", False))
        is_candidate = bool(item.get("is_candidate", True))
        entity_type = str(item.get("entity_type", "person"))
        profile_url = item.get("profile_url")

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
                "profile_url": profile_url
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
                "profile_url": profile_url
            })
        else:
            candidates_to_analyze.append({
                "name": name,
                "headline": headline or None,
                "comment": comment_text,
                "entity_type": entity_type,
                "profile_url": profile_url
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
                "phone": None
            })
        return evaluated_results

    try:
        client = genai.Client(api_key=api_key)
        
        sorted_candidates = sorted(
            candidates_to_analyze,
            key=lambda x: (str(x.get("name", "")).lower(), str(x.get("comment", "")).lower())
        )

        input_data = json.dumps(sorted_candidates)
        
        prompt = f"""
You are a deterministic B2B lead qualification and enrichment system.
Analyze the following structured list of LinkedIn commenter candidates.

You have access to Google Search. You MUST use it to enrich and verify publicly available information for these candidates based on their name, headline, and comment context.

ENRICHMENT & VERIFICATION RULES:
1. Verify the person/company identity matches the candidate. Do not treat a random same-name search result as the candidate.
2. If `entity_type` is "company", do not create a normal person lead unless the comment explicitly indicates buying intent from that company.
3. Fill missing company/role information only when strong public evidence exists.
4. Find a publicly listed business email/phone ONLY when the public source clearly associates it with that person/business. NEVER guess or fabricate missing information. Return null if unavailable.
5. Provide the supporting public source URL in `source_reference`.

DETERMINISTIC QUALIFICATION MATRIX:
1. QUALIFIED LEAD (`lead`: true):
   - Comment explicitly seeks solutions, software, vendor services, demos, pricing, or implementation details.
   - Comment describes an active business challenge or implementation project.
   - Commenter role/headline indicates a decision maker, evaluator, or buyer AND comment is non-generic.
   - Outputs:
     * `lead_score`: 70 to 100
     * `intent`: "High" or "Medium"
     * `lead_type`: "Decision Maker", "Evaluator", or "Prospect"
     * `first_name` / `last_name`: Derived from verified full name.
     * `name` (full_name): Verified candidate name.
     * `company`: Verified company, otherwise null.
     * `role`: Verified role/headline, otherwise null.
     * `business_need`: Inferred only from comment + supporting evidence.
     * `reason`: Concise explanation of why this is a qualified lead.
     * `email` / `phone`: ONLY if publicly and confidently associated.
     * `source`: "linkedin_post_web_enriched"
     * `source_reference`: URL of the public source evidence.

2. DISQUALIFIED COMMENT (`lead`: false):
   - Generic praise or politeness ("Great post", "Agreed").
   - Personal anecdotes without business software/service intent.
   - Outputs:
     * `lead_score`: 0 to 39
     * `intent`: "Low" or null
     * `lead_type`: null
     * `business_need`: null
     * `reason`: "Generic or non-buying comment"
     * `source`: "linkedin_post"

CRITICAL: Return a JSON array containing the analyzed objects for ALL input items in the EXACT SAME ORDER as provided. Do not invent a profile_url, use the provided one or null.

Input candidates:
{input_data}
"""

        response = client.models.generate_content(
            model='gemini-3.7-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                seed=42,
                response_mime_type="application/json",
                tools=[types.Tool(google_search=types.GoogleSearch())]
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
                    item["name"] = item.get("name") or cand.get("name") or "Unknown"
                    item["first_name"] = item.get("first_name") or (item["name"].split(" ")[0] if item["name"] else None)
                    item["last_name"] = item.get("last_name") or (" ".join(item["name"].split(" ")[1:]) if item["name"] and " " in item["name"] else None)
                    item["headline"] = item.get("headline") or cand.get("headline")
                    item["email"] = item.get("email") or None
                    item["phone"] = item.get("phone") or None
                    item["profile_url"] = cand.get("profile_url") or None
                    item["source"] = item.get("source") or "linkedin_post_web_enriched"
                    item["source_reference"] = item.get("source_reference") or None
                    evaluated_results.append(item)

        return evaluated_results
    except Exception as e:
        print(f"Gemini Analysis Error: {str(e)}")
        raise e

