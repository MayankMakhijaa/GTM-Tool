import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from google import genai
from google.genai import types

def optimize_linkedin_profile(extracted_profile: Dict[str, Any], icp_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Use Gemini to evaluate the extracted LinkedIn profile and generate structured lead-generation recommendations.
    Uses a single structured request for cost control and fast evaluation.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment.")

    client = genai.Client(api_key=api_key)
    
    # Deterministic preparation
    profile_data = extracted_profile.get("profile", extracted_profile) if isinstance(extracted_profile, dict) else {}
    
    # Prepare stripped profile to reduce tokens
    stripped_profile = {
        "name": profile_data.get("name"),
        "headline": profile_data.get("headline"),
        "location": profile_data.get("location"),
        "current_position": profile_data.get("current_position"),
        "about": profile_data.get("about"),
        "experience": profile_data.get("experience", []),
        "education": profile_data.get("education", []),
        "skills": profile_data.get("skills", []),
        "certifications": profile_data.get("certifications", []),
        "projects": profile_data.get("projects", []),
        "featured": profile_data.get("featured", []),
        "honors_awards": profile_data.get("honors_awards", []),
        "publications": profile_data.get("publications", []),
        "courses": profile_data.get("courses", []),
        "volunteer_experience": profile_data.get("volunteer_experience", []),
        "languages": profile_data.get("languages", []),
        "recommendations": profile_data.get("recommendations", [])
    }
    
    icp_json = json.dumps(icp_profile, indent=2) if icp_profile else "No ICP context provided."
    profile_json = json.dumps(stripped_profile, indent=2)

    prompt = f"""
You are an elite executive LinkedIn lead-generation strategist and professional positioning consultant.

GTM STRATEGY / ICP CONTEXT:
The user is targeting the following offer and audience:
{icp_json}
Ensure the optimization strongly aligns with this Go-To-Market strategy.

INPUT EXTRACTED PROFILE:
{profile_json}

INSTRUCTIONS:
Analyze the user's profile against their ICP. 
For EVERY applicable section in the profile (headline, about, experience, education, skills, certifications, projects, featured, honors_awards, publications, courses, volunteer_experience, languages, recommendations), you MUST classify it based on its presence and ICP relevance.
DO NOT EQUATE 'empty section = bad profile'. An empty section like 'languages' might be MISSING_OPTIONAL if irrelevant to ICP.

CLASSIFICATIONS:
- PRESENT_STRONG: Exists and is aligned with the ICP/profile objective.
- PRESENT_WEAK: Exists but could be significantly improved for ICP alignment, clarity, positioning.
- PRESENT_IRRELEVANT: Exists but contributes little/nothing toward the ICP. (Do not automatically recommend deleting it).
- MISSING_RELEVANT: Genuinely empty (an empty array or null) AND would materially help the ICP objective.
- MISSING_OPTIONAL: Genuinely empty BUT not important enough to affect the current objective.
- NOT_APPLICABLE: Does not meaningfully apply.

You must return a structured JSON response matching the following schema.

OUTPUT SCHEMA:
{{
  "overall_score": <integer 0-100 reflecting ICP relevance and profile objective, weighted transparently. Don't simply average equal weights>,
  "score_rationale": "<brief explanation of how the score was calculated based on ICP relevance>",
  "section_analysis": [
    {{
      "section": "<section_name>",
      "status": "<PRESENT_STRONG|PRESENT_WEAK|PRESENT_IRRELEVANT|MISSING_RELEVANT|MISSING_OPTIONAL|NOT_APPLICABLE>",
      "relevance": "<HIGH|MEDIUM|LOW>",
      "score": <0-100 or null if not scored>,
      "reason": "<explanation of the status>",
      "issues": ["list of issues if any"],
      "suggestions": ["list of improvement suggestions"]
    }}
  ],
  "recommendations": [
    {{
      "priority": "<HIGH|MEDIUM|LOW>",
      "section": "<section_name>",
      "problem": "<description>",
      "why_it_matters": "<impact explanation>",
      "recommended_action": "<what to do>",
      "original_content": "<actual original content if applicable, else null>",
      "suggested_content": "<suggested draft if applicable, else null>",
      "reason": "<reasoning for suggestion>"
    }}
  ]
}}
"""

    # We use gemini-1.5-flash as it's the widely available and reliable API version for typical genai usage
    # We fallback to older models if necessary, but 1.5-flash is ideal for speed and JSON output.
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            seed=42,
            response_mime_type="application/json"
        )
    )

    result_text = response.text
    if not result_text:
        raise ValueError("Gemini returned an empty response.")

    result_data = json.loads(result_text)
    
    return {
        "analyzed_at": datetime.now().isoformat(),
        "overall_score": result_data.get("overall_score", 0),
        "score_rationale": result_data.get("score_rationale", ""),
        "section_analysis": result_data.get("section_analysis", []),
        "recommendations": result_data.get("recommendations", [])
    }
