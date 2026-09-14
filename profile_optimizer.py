import os
import json
from typing import Dict, Any, List
from datetime import datetime
from google import genai
from google.genai import types


def optimize_linkedin_profile(extracted_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use Gemini to evaluate the extracted LinkedIn profile and generate structured lead-generation recommendations.
    Uses a single structured request for cost control and fast evaluation.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment.")

    client = genai.Client(api_key=api_key)

    profile_data = extracted_profile.get("profile", extracted_profile)
    profile_json = json.dumps(profile_data, indent=2)

    prompt = f"""
You are an elite executive LinkedIn lead-generation strategist and professional positioning consultant.

MASTER OPTIMIZATION OBJECTIVE:
Your primary objective is to optimize the user's LinkedIn profile to generate more relevant LEADS, BUSINESS OPPORTUNITIES, HIGH-VALUE CONVERSATIONS, and PROFESSIONAL OPPORTUNITIES.
The user is optimizing THEIR OWN LinkedIn profile.

HIERARCHICAL ANALYSIS RULES:
1. IDENTIFY ROLE & IDENTITY: Inspect the extracted profile to determine the user's core professional role:
   - Founder / Co-Founder / CEO / Managing Director / Business Owner / Agency Owner
   - Consultant / Freelancer / Independent Advisor
   - Professional / Employee / Specialist
   - Student / Early Career
   - Other

2. POSITIONING STRATEGY BASED ON ROLE:
   - FOR FOUNDERS / CEOS / BUSINESS OWNERS:
     * DO NOT optimize the profile as if they are searching for employment.
     * NEVER recommend "Open to Work", "Looking for opportunities", "Seeking Software Engineer roles", job-search keywords, or resume framing.
     * Instead, optimize toward: attracting potential clients, attracting qualified leads, communicating company value proposition, establishing market authority, increasing trust, encouraging inbound business inquiries, and improving visitor-to-lead conversion.
     * Frame headline/about to answer: "Does this make the target prospect immediately understand what this founder/company offers and why they should start a conversation?"
   - FOR CONSULTANTS / FREELANCERS / EMPLOYEES / STUDENTS:
     * Focus on demonstrating deep domain expertise, establishing authority, attracting business/client/career opportunities, and driving meaningful inbound conversations.

3. ABSOLUTE TRUTHFULNESS CONSTRAINTS:
   - NEVER invent companies, clients, projects, achievements, technologies, job titles, metrics, revenue, years of experience, or credentials.
   - Work strictly from the user's actual profile facts.
   - Do NOT assume the user is looking for a job unless the profile explicitly indicates that.

4. ACTION TYPES PER RECOMMENDATION:
   For every profile section recommendation, assign one of three action_types:
   - "none": When current content is already effective or no change is needed (`change_required`: false, `suggested`: null).
   - "copy": When suggesting specific replacement or refined text for existing content (Headline, About, Experience bullet points, Education details) (`change_required`: true, `suggested`: "<actual recommended text to copy>").
   - "ask_chatgpt": When recommending that the user CREATE or ADD something new that doesn't currently exist (e.g., adding a missing Projects section, missing Featured post, missing certifications) where they need guidance to draft content (`change_required`: true, `suggested`: "<specific advice/prompt context on what to create>").

INPUT EXTRACTED PROFILE:
{profile_json}

OUTPUT INSTRUCTIONS:
Return a SINGLE JSON object with this exact schema:
{{
  "user_role_category": "Founder / CEO" | "Consultant / Freelancer" | "Professional / Employee" | "Student / Early Career" | "Other",
  "overall_score": 82,
  "category_scores": {{
    "positioning": 85,
    "headline": 80,
    "about": 75,
    "experience": 82,
    "skills": 88,
    "completeness": 78
  }},
  "summary_assessment": "Concise overview of current lead-generation positioning, target audience alignment, and key improvement areas.",
  "recommendations": [
    {{
      "section": "headline",
      "title": "Profile Headline",
      "change_required": true,
      "current": "<actual extracted headline>",
      "suggested": "<strategic value-focused headline>",
      "reason": "Explains why this headline attracts more qualified leads and business conversations.",
      "priority": "high",
      "action_type": "copy"
    }},
    {{
      "section": "about",
      "title": "About / Summary",
      "change_required": true,
      "current": "<actual extracted about>",
      "suggested": "<prospect-focused summary framing core offer, credibility, and call-to-action>",
      "reason": "Sharpens value proposition and visitor-to-lead conversion.",
      "priority": "high",
      "action_type": "copy"
    }},
    {{
      "section": "experience",
      "title": "Experience Descriptions",
      "change_required": true,
      "current": "<actual experience>",
      "suggested": "<outcome and authority-focused bullet points>",
      "reason": "Replaces generic duty listings with high-trust achievements.",
      "priority": "medium",
      "action_type": "copy"
    }},
    {{
      "section": "skills",
      "title": "Skills & Core Competencies",
      "change_required": true,
      "current": "<actual list of skills>",
      "suggested": "<recommended core skills and domain keywords>",
      "reason": "Aligns skill profile with target prospect search and domain authority.",
      "priority": "medium",
      "action_type": "copy"
    }},
    {{
      "section": "projects",
      "title": "Featured Projects",
      "change_required": true,
      "current": "<actual projects or No projects found>",
      "suggested": "Add key client projects or case studies showcasing problem-solving capability.",
      "reason": "Providing tangible proof of execution increases prospect confidence.",
      "priority": "medium",
      "action_type": "ask_chatgpt"
    }},
    {{
      "section": "featured",
      "title": "Featured Section",
      "change_required": true,
      "current": "<actual featured content or Not available>",
      "suggested": "Feature high-performing posts, client testimonials, or case study media.",
      "reason": "Increases visual proof of authority for profile visitors.",
      "priority": "low",
      "action_type": "ask_chatgpt"
    }},
    {{
      "section": "certifications",
      "title": "Certifications & Licenses",
      "change_required": false,
      "current": "<actual certifications>",
      "suggested": null,
      "reason": "Certifications section is adequately presented.",
      "priority": "none",
      "action_type": "none"
    }},
    {{
      "section": "education",
      "title": "Education",
      "change_required": false,
      "current": "<actual education>",
      "suggested": null,
      "reason": "Education details are clear and complete.",
      "priority": "none",
      "action_type": "none"
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
        "user_role_category": result_data.get("user_role_category", "Professional / Employee"),
        "overall_score": result_data.get("overall_score", 75),
        "category_scores": result_data.get("category_scores", {}),
        "summary_assessment": result_data.get("summary_assessment", ""),
        "recommendations": result_data.get("recommendations", [])
    }
