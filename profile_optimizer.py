import os
import json
from typing import Dict, Any, List
from datetime import datetime
from google import genai
from google.genai import types


def optimize_linkedin_profile(extracted_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use Gemini to evaluate the extracted LinkedIn profile and generate structured optimization recommendations.
    Uses a single structured request for cost control and fast evaluation.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment.")

    client = genai.Client(api_key=api_key)

    profile_data = extracted_profile.get("profile", extracted_profile)
    profile_json = json.dumps(profile_data, indent=2)

    prompt = f"""
You are an expert executive LinkedIn profile strategist, career brand consultant, and recruiter SEO expert.
Analyze the following extracted LinkedIn profile and generate data-driven optimization recommendations.

CRITICAL CONSTRAINTS:
- Do NOT invent fake companies, degrees, unearned achievements, or hallucinated metrics that are not supported by the profile.
- Work ONLY from the provided profile data and general professional branding best practices.
- For sections where rewriting improves recruiter discoverability, keyword relevance, or executive positioning, provide actionable suggestions.
- For sections that are already clear and effective or missing without enough context, provide helpful guidance or set suggested to "No changes recommended".

INPUT EXTRACTED PROFILE:
{profile_json}

OUTPUT INSTRUCTIONS:
Return a SINGLE JSON object with the following exact schema:
{{
  "overall_score": 78,
  "category_scores": {{
    "positioning": 82,
    "headline": 76,
    "about": 71,
    "experience": 80,
    "skills": 84,
    "completeness": 75
  }},
  "summary_assessment": "Concise summary of profile strengths and primary optimization targets.",
  "recommendations": [
    {{
      "section": "headline",
      "title": "Profile Headline",
      "current": "<actual extracted headline>",
      "suggested": "<strategic keyword-rich headline suggestion>",
      "reason": "Concise explanation of positioning impact and recruiter discoverability.",
      "priority": "high"
    }},
    {{
      "section": "about",
      "title": "About / Summary",
      "current": "<actual extracted about or Not available>",
      "suggested": "<first-person executive summary framing key value proposition>",
      "reason": "Enhances narrative hook, core competencies, and call to action.",
      "priority": "high"
    }},
    {{
      "section": "experience",
      "title": "Experience Descriptions",
      "current": "<actual experience description>",
      "suggested": "<action-oriented bullet points emphasizing scope, technologies, and business outcomes>",
      "reason": "Replaces generic duty listings with achievement-oriented bullet points.",
      "priority": "medium"
    }},
    {{
      "section": "skills",
      "title": "Skills & Core Competencies",
      "current": "<actual list of skills>",
      "suggested": "<recommended industry-standard keywords and skills list>",
      "reason": "Aligns skill profile with target ATS and recruiter search filters.",
      "priority": "medium"
    }},
    {{
      "section": "featured",
      "title": "Featured Section",
      "current": "<actual featured content or Not available>",
      "suggested": "<recommendations for media, posts, articles, or case studies to feature>",
      "reason": "Increases visual proof of expertise.",
      "priority": "low"
    }},
    {{
      "section": "certifications",
      "title": "Certifications & Licenses",
      "current": "<actual certifications or Not available>",
      "suggested": "<suggested high-value certifications or formatting>",
      "reason": "Highlights credible industry credentials.",
      "priority": "low"
    }},
    {{
      "section": "projects",
      "title": "Featured Projects",
      "current": "<actual projects or Not available>",
      "suggested": "<suggested project highlights or formatting>",
      "reason": "Demonstrates practical execution.",
      "priority": "low"
    }},
    {{
      "section": "education",
      "title": "Education",
      "current": "<actual education>",
      "suggested": "<formatting or background details>",
      "reason": "Ensures complete academic profile.",
      "priority": "low"
    }},
    {{
      "section": "positioning",
      "title": "Overall Strategic Positioning",
      "current": "<summary of current market positioning>",
      "suggested": "<recommended market positioning taglines and niche focus>",
      "reason": "Sharpen target audience alignment.",
      "priority": "high"
    }}
  ]
}}
"""

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
        "tenant_id": extracted_profile.get("tenant_id", "default_tenant"),
        "user_id": extracted_profile.get("user_id", "pro_user"),
        "analyzed_at": datetime.now().isoformat(),
        "overall_score": result_data.get("overall_score", 75),
        "category_scores": result_data.get("category_scores", {}),
        "summary_assessment": result_data.get("summary_assessment", ""),
        "recommendations": result_data.get("recommendations", [])
    }
