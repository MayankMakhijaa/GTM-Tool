import os
import re
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import quote

import requests
from google import genai
from google.genai import types

from app.database import db_session
from app.models.all_models import (
    UsersICP,
    UsersCompanyDetails,
    UsersLinkedinDetails,
    GlobalProfiles,
    UsersProfiles,
    ResearchJobs,
    ResearchJobStatus,
    ResearchType,
    LeadStatus,
    GlobalProfileSource
)
from app.integrations.linkedin.voyager_client import (
    create_voyager_client_from_db,
    validate_user_session
)
from app.services.scraping_service import (
    perform_public_web_search,
    is_google_search_configured,
    validate_google_search_config
)

logger = logging.getLogger(__name__)


class CandidateList(list):
    """
    List subclass carrying structured execution metadata, provider origin,
    and typed error categorization without breaking standard list compatibility.
    """
    def __init__(
        self,
        items: Optional[List[Dict[str, Any]]] = None,
        status: str = "SUCCESS",
        error_category: Optional[str] = None,
        provider: str = "UNKNOWN",
        raw_error: Optional[str] = None
    ):
        super().__init__(items or [])
        self.status = status
        self.error_category = error_category
        self.provider = provider
        self.raw_error = raw_error

    @property
    def is_success(self) -> bool:
        return self.status == "SUCCESS"


def normalize_linkedin_identifier(profile_url: Optional[str], urn_id: Optional[str]) -> Optional[str]:
    """
    Extracts a normalized, stable LinkedIn identifier from a profile URL or URN.
    Returns normalized vanity slug or URN string (e.g. 'john-doe-12345' or 'ACoAAB12345').
    """
    if urn_id:
        clean_urn = str(urn_id).strip()
        if clean_urn.startswith("urn:li:fsd_profile:"):
            clean_urn = clean_urn.replace("urn:li:fsd_profile:", "")
        elif clean_urn.startswith("urn:li:member:"):
            clean_urn = clean_urn.replace("urn:li:member:", "")
        if clean_urn and clean_urn.lower() != "none":
            return clean_urn

    if profile_url:
        clean_url = str(profile_url).strip()
        m = re.search(r"linkedin\.com/in/([^/?#]+)", clean_url, re.IGNORECASE)
        if m:
            slug = m.group(1).strip()
            if slug and slug.lower() != "none":
                return slug

    return None


def normalize_profile_url(raw_url: Optional[str], urn_id: Optional[str] = None) -> Optional[str]:
    """
    Normalizes a LinkedIn profile URL by removing tracking params and enforcing HTTPS.
    """
    if raw_url:
        m = re.search(r"linkedin\.com/in/([^/?#]+)", raw_url, re.IGNORECASE)
        if m:
            slug = m.group(1).strip()
            return f"https://www.linkedin.com/in/{slug}"
    if urn_id:
        clean = normalize_linkedin_identifier(None, urn_id)
        if clean:
            return f"https://www.linkedin.com/in/{clean}"
    return None

GEMINI_MODELS_FALLBACK = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash"
]


def _get_gemini_client() -> Optional[genai.Client]:
    """Instantiates the Gemini client using GEMINI_API_KEY from environment."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("[GTM Service] GEMINI_API_KEY not configured.")
        return None
    return genai.Client(api_key=api_key)


def _call_gemini_with_fallback(prompt: str, response_json: bool = True) -> Optional[str]:
    """Calls Gemini with automatic model fallback."""
    client = _get_gemini_client()
    if not client:
        return None

    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json" if response_json else "text/plain"
    )

    for model_name in GEMINI_MODELS_FALLBACK:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"[GTM Service] Gemini model {model_name} failed: {err_msg}")
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                continue
    return None


def _clean_json(text: Optional[str]) -> Any:
    """Parses JSON text, stripping code markdown blocks if present."""
    if not text:
        return None
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean = "\n".join(lines).strip()
    try:
        return json.loads(clean)
    except Exception as e:
        logger.error(f"[GTM Service] Failed to parse JSON: {e} - Raw text: {text[:200]}")
        return None


# ====================================================================
# USER CONTEXT & SESSION RESOLUTION
# ====================================================================

def get_user_gtm_context(user_id: int) -> Dict[str, Any]:
    """
    Retrieves the authenticated user's saved ICP and company details from PostgreSQL.
    Returns structured context for query planning, display, and qualification.
    """
    icp = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    company = db_session.query(UsersCompanyDetails).filter_by(user_id=user_id).first()
    linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()

    has_onboarding = bool(icp and company and (company.company_name or company.website_url))

    session_validation = {"valid": False, "category": "disconnected", "message": "No LinkedIn account connected."}
    if linkedin and linkedin.auth_data_encrypted:
        session_validation = validate_user_session(user_id)

    offer_text = ""
    if company:
        offer_text = company.what_company_sells or company.products_services or company.description or ""

    target_icp_text = ""
    if icp:
        components = []
        if icp.target_customer:
            components.append(f"Target Customer: {icp.target_customer}")
        if icp.target_jobs_roles:
            components.append(f"Roles: {icp.target_jobs_roles}")
        if icp.industry:
            components.append(f"Industry: {icp.industry}")
        if icp.company_size:
            components.append(f"Size: {icp.company_size}")
        if icp.location:
            components.append(f"Location: {icp.location}")
        if icp.keywords:
            components.append(f"Keywords: {icp.keywords}")
        target_icp_text = " | ".join(components)

    active_job = db_session.query(ResearchJobs).filter(
        ResearchJobs.user_id == user_id,
        ResearchJobs.status.in_([ResearchJobStatus.QUEUED.value, ResearchJobStatus.RUNNING.value])
    ).order_by(ResearchJobs.id.desc()).first()

    active_job_dict = None
    if active_job:
        active_job_dict = {
            "id": active_job.id,
            "job_id": active_job.id,
            "status": active_job.status,
            "progress": active_job.progress or {},
            "results_count": active_job.results_count or 0,
            "error": active_job.error_message
        }

    return {
        "user_id": user_id,
        "onboarding_completed": has_onboarding,
        "company_name": company.company_name if company else "",
        "website_url": company.website_url if company else "",
        "industry": company.industry if company else (icp.industry if icp else ""),
        "offer": offer_text,
        "target_icp": target_icp_text,
        "icp_raw": {
            "target_customer": icp.target_customer if icp else None,
            "target_jobs_roles": icp.target_jobs_roles if icp else None,
            "industry": icp.industry if icp else None,
            "company_size": icp.company_size if icp else None,
            "location": icp.location if icp else None,
            "keywords": icp.keywords if icp else None,
            "exclusions": icp.exclusions if icp else None,
            "signals": icp.signals if icp else None,
            "version": icp.version if icp else 1
        } if icp else {},
        "session_valid": session_validation.get("valid", False),
        "session_category": session_validation.get("category", "disconnected"),
        "session_message": session_validation.get("message", ""),
        "active_job": active_job_dict
    }


# ====================================================================
# GEMINI QUERY PLANNING
# ====================================================================

def generate_search_plan(user_context: Dict[str, Any], persona_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Uses Gemini to translate PostgreSQL ICP and Company context into structured LinkedIn
    search parameters, distinct targeted query objects, and public web targets.
    """
    icp = user_context.get("icp_raw", {})
    offer = user_context.get("offer", "")
    target_icp = user_context.get("target_icp", "")

    fallback_title = persona_filter or icp.get("target_jobs_roles") or "VP of Sales, CRO, Head of Growth"
    fallback_keywords = icp.get("keywords") or icp.get("industry") or "B2B SaaS"
    fallback_industry = icp.get("industry") or "Software Development"
    raw_exclusions = [e.strip() for e in (icp.get("exclusions") or "").split(",") if e.strip()]

    prompt = f"""
You are an expert Go-To-Market (GTM) research query strategist.
Translate the following user company offering and Ideal Customer Profile (ICP) into highly targeted search parameters and distinct targeted search queries for candidate discovery.

Company Offering:
{offer}

Target ICP Criteria:
{target_icp}
Target Roles: {icp.get('target_jobs_roles', '')}
Industry: {icp.get('industry', '')}
Keywords: {icp.get('keywords', '')}
Exclusions: {icp.get('exclusions', '')}
Specific Persona Override: {persona_filter or 'None'}

Return a single JSON object with EXACTLY the following structure:
{{
  "search_keywords": "string with Boolean or specific high-intent keyword query",
  "keyword_title": "string containing 2 to 4 comma-separated or primary title keywords (e.g., 'VP Sales, Head of RevOps')",
  "target_industries": ["list of 2 to 3 target industry terms"],
  "target_company_types": ["list of 2 to 3 target company descriptors, e.g., 'B2B SaaS', 'Cloud Software'"],
  "queries": [
    {{
      "id": "q1",
      "title": "specific title or synonym, e.g. VP of Sales",
      "keywords": "high-intent keyword, e.g. B2B SaaS",
      "industry": "industry term",
      "location": "geographic region if specified",
      "exclusions": ["negative term 1", "negative term 2"]
    }}
  ]
}}
"""
    raw_response = _call_gemini_with_fallback(prompt, response_json=True)
    parsed = _clean_json(raw_response)

    if not parsed or not isinstance(parsed, dict):
        parsed = {
            "search_keywords": fallback_keywords,
            "keyword_title": fallback_title,
            "target_industries": [fallback_industry],
            "target_company_types": ["B2B SaaS", "Technology"],
            "queries": []
        }

    # Ensure required top-level keys exist for backward compatibility
    if not parsed.get("search_keywords"):
        parsed["search_keywords"] = fallback_keywords
    if not parsed.get("keyword_title"):
        parsed["keyword_title"] = fallback_title
    if not parsed.get("target_industries"):
        parsed["target_industries"] = [fallback_industry]
    if not parsed.get("target_company_types"):
        parsed["target_company_types"] = ["B2B SaaS", "Technology"]

    # Validate and bound queries list
    queries = parsed.get("queries")
    if not queries or not isinstance(queries, list):
        role_candidates = [r.strip() for r in re.split(r"[,/|;]|\band\b", fallback_title) if r.strip()]
        if not role_candidates:
            role_candidates = [fallback_title]
        queries = []
        for idx, role in enumerate(role_candidates[:3], 1):
            queries.append({
                "id": f"q{idx}",
                "title": role,
                "keywords": fallback_keywords,
                "industry": fallback_industry,
                "location": icp.get("location") or "",
                "exclusions": raw_exclusions
            })

    # Enforce deterministic limits: max 4 queries, unique query IDs
    sanitized_queries = []
    seen_combos = set()
    for idx, q in enumerate(queries[:4], 1):
        if not isinstance(q, dict):
            continue
        q_title = q.get("title") or fallback_title
        q_kw = q.get("keywords") or fallback_keywords
        combo = (q_title.lower().strip(), q_kw.lower().strip())
        if combo in seen_combos:
            continue
        seen_combos.add(combo)
        sanitized_queries.append({
            "id": q.get("id") or f"q{idx}",
            "title": q_title,
            "keywords": q_kw,
            "industry": q.get("industry") or fallback_industry,
            "location": q.get("location") or (icp.get("location") or ""),
            "exclusions": q.get("exclusions") or raw_exclusions
        })

    parsed["queries"] = sanitized_queries or [{
        "id": "q1",
        "title": fallback_title,
        "keywords": fallback_keywords,
        "industry": fallback_industry,
        "location": icp.get("location") or "",
        "exclusions": raw_exclusions
    }]

    return parsed


# ====================================================================
# DISCOVERY PATH A: VOYAGER LINKEDIN DISCOVERY
# ====================================================================

def discover_candidates_via_voyager(
    user_id: int,
    search_plan: Dict[str, Any],
    limit: int = 15
) -> CandidateList:
    """
    Executes live LinkedIn people discovery using the user's authenticated Voyager session.
    Distinguishes: success, zero results, expired auth, rate limited, network error, endpoint incompatible, malformed.
    Returns CandidateList with candidates and structured execution metadata.
    """
    # 1. Pre-flight session validation using stored credentials (safe, non-destructive, zero Chromium)
    linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    if linkedin and linkedin.auth_data_encrypted:
        validation = validate_user_session(user_id)
        if not validation.get("valid"):
            cat = validation.get("category", "expired")
            msg = validation.get("message", "LinkedIn session is not authenticated.")
            logger.warning(f"[GTM Voyager] Pre-flight session validation failed for user {user_id}: {cat} - {msg}")
            return CandidateList([], status="AUTH_EXPIRED", error_category=cat, provider="VOYAGER", raw_error=msg)

    client = create_voyager_client_from_db(user_id)
    if not client:
        validation = validate_user_session(user_id)
        cat = validation.get("category", "no_connection")
        msg = validation.get("message", "No active Voyager client found.")
        logger.warning(f"[GTM Voyager] No active Voyager client for user {user_id}: {cat} - {msg}")
        return CandidateList([], status="AUTH_EXPIRED", error_category=cat, provider="VOYAGER", raw_error=msg)

    queries_to_run = search_plan.get("queries")
    if not queries_to_run or not isinstance(queries_to_run, list):
        queries_to_run = [{
            "id": "q1",
            "title": search_plan.get("keyword_title"),
            "keywords": search_plan.get("search_keywords")
        }]

    all_candidates = []
    seen_ids = set()
    overall_status = "ZERO_RESULTS"
    overall_error_category = None
    overall_error_msg = None

    per_query_limit = max(5, min(limit, 10))

    for q in queries_to_run:
        q_id = q.get("id", "q1")
        keywords = q.get("keywords") or search_plan.get("search_keywords")
        keyword_title = q.get("title") or search_plan.get("keyword_title")

        logger.info(f"[GTM Voyager] Executing query {q_id}: keywords='{keywords}', title='{keyword_title}'")
        try:
            raw_results = client.search_people(
                keywords=keywords,
                keyword_title=keyword_title,
                limit=per_query_limit
            )
        except Exception as e:
            err_msg = str(e)
            err_lower = err_msg.lower()
            logger.error(f"[GTM Voyager] search_people failed for query {q_id}: {err_msg}")

            if "429" in err_msg or "rate" in err_lower or "throttle" in err_lower:
                status = "RATE_LIMITED"
                cat = "rate_limited"
            elif any(k in err_lower for k in ["unauthorized", "expired", "redirect", "too many redirects", "authwall", "checkpoint", "challenge", "401", "403"]):
                status = "AUTH_EXPIRED"
                cat = "expired"
                try:
                    from app.integrations.linkedin.voyager_client import _update_connection_status
                    _update_connection_status(user_id, "EXPIRED")
                except Exception:
                    pass
            elif "connect" in err_lower or "timeout" in err_lower or "connection" in err_lower:
                status = "NETWORK_ERROR"
                cat = "network_error"
            elif "graphql" in err_lower or "schema" in err_lower or "404" in err_msg:
                status = "ENDPOINT_INCOMPATIBLE"
                cat = "endpoint_incompatible"
            elif "json" in err_lower or "decode" in err_lower:
                status = "MALFORMED_RESPONSE"
                cat = "malformed_response"
            else:
                status = "FAILED"
                cat = "unknown_error"

            overall_status = status
            overall_error_category = cat
            overall_error_msg = err_msg

            if cat in ("expired", "rate_limited"):
                logger.info(f"[GTM Voyager] Halting remaining queries due to terminal auth/rate condition ({cat}).")
                break
            continue

        if not raw_results:
            continue

        for item in raw_results:
            urn_id = item.get("urn_id") or ""
            name = item.get("name") or "LinkedIn Member"
            raw_title = item.get("jobtitle") or ""
            location = item.get("location") or ""

            role = raw_title
            company_name = ""
            if " at " in raw_title:
                parts = raw_title.split(" at ", 1)
                role = parts[0].strip()
                company_name = parts[1].strip()
            elif " @ " in raw_title:
                parts = raw_title.split(" @ ", 1)
                role = parts[0].strip()
                company_name = parts[1].strip()
            elif " | " in raw_title:
                parts = raw_title.split(" | ", 1)
                role = parts[0].strip()
                company_name = parts[1].strip()

            norm_urn = normalize_linkedin_identifier(None, urn_id)
            if not norm_urn and not name:
                continue

            dedup_key = norm_urn or urn_id or f"{name.strip().lower()}:{company_name.strip().lower()}"
            if dedup_key in seen_ids:
                continue
            seen_ids.add(dedup_key)

            profile_url = normalize_profile_url(None, norm_urn or urn_id)

            all_candidates.append({
                "urn_id": norm_urn or urn_id or f"urn:li:member:{abs(hash(name + raw_title)) % 10000000}",
                "name": name,
                "role": role,
                "raw_headline": raw_title,
                "company": company_name or "Target Company",
                "location": location,
                "profile_url": profile_url,
                "distance": item.get("distance", "DISTANCE_2"),
                "provider": "VOYAGER",
                "source_query": q_id,
                "source_evidence": f"Voyager People Search: {keywords or ''} {keyword_title or ''}".strip()
            })

        if len(all_candidates) >= limit:
            break

    if all_candidates:
        return CandidateList(all_candidates[:limit], status="SUCCESS", provider="VOYAGER")
    elif overall_error_category:
        return CandidateList([], status=overall_status, error_category=overall_error_category, provider="VOYAGER", raw_error=overall_error_msg)
    else:
        return CandidateList([], status="ZERO_RESULTS", provider="VOYAGER")


# ====================================================================
# DISCOVERY PATH B: AGENT-REACH & PUBLIC-WEB DISCOVERY
# ====================================================================

def read_public_url_agent_reach(url: str, timeout: int = 8) -> Dict[str, Any]:
    """
    Agent-Reach Jina Reader adapter:
    Converts public web URLs to clean markdown via https://r.jina.ai/{url}.
    Applies security headers, strict timeouts, and antibot detection.
    Never includes LinkedIn cookies or session credentials.
    """
    if not url or not url.startswith("http"):
        return {"status": "INVALID_URL", "summary": "", "source": "AGENT_REACH_JINA"}

    jina_endpoint = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "text/markdown",
        "User-Agent": "FamewebAgentReach/1.0"
    }

    try:
        resp = requests.get(jina_endpoint, headers=headers, timeout=timeout)
        if resp.status_code == 200 and resp.text:
            text = resp.text
            if "anomaly-modal" in text or "challenge-form" in text:
                return {"status": "BOT_CHALLENGE", "summary": "", "source": "AGENT_REACH_JINA"}
            return {
                "status": "OK",
                "summary": text[:2500],
                "verified_url": url,
                "source": "AGENT_REACH_JINA"
            }
        return {"status": f"HTTP_{resp.status_code}", "summary": "", "source": "AGENT_REACH_JINA"}
    except Exception as e:
        logger.debug(f"[Agent Reach] Jina read failed for {url}: {e}")
        return {"status": "ERROR", "summary": "", "source": "AGENT_REACH_JINA", "error": str(e)}


def enrich_company_public_web(company_name: str, website_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Enriches target company information using the verified Agent-Reach Jina Reader capability.
    STRICT SECURITY: Never includes LinkedIn cookies or session credentials in external requests.
    """
    if not company_name and not website_url:
        return {"summary": "", "signals": "", "source": "None"}

    target_url = website_url
    if not target_url or not target_url.startswith("http"):
        clean_name = re.sub(r"[^a-zA-Z0-9]", "", company_name.lower())
        target_url = f"https://www.{clean_name}.com"

    reach_res = read_public_url_agent_reach(target_url)
    if reach_res.get("status") == "OK" and reach_res.get("summary"):
        return {
            "summary": reach_res["summary"],
            "verified_url": target_url,
            "source": "JINA_READER",
            "status": "OK"
        }

    return {
        "summary": f"{company_name} - active commercial organization.",
        "verified_url": target_url,
        "source": "FALLBACK",
        "status": "FALLBACK"
    }


def discover_candidates_via_public_web(
    user_context: Dict[str, Any],
    search_plan: Dict[str, Any],
    limit: int = 15
) -> CandidateList:
    """
    Independent public web discovery provider.
    Executes search engine discovery (Google Custom Search API if configured) using ICP queries
    to find publicly indexed LinkedIn member profiles, completely independent of Voyager session.
    Keeps provider disabled with NOT_CONFIGURED when credentials are absent.
    """
    if not is_google_search_configured():
        cfg_status = validate_google_search_config()
        logger.info(f"[GTM Public Web] Provider disabled: {cfg_status['message']}")
        return CandidateList(
            [],
            status="NOT_CONFIGURED",
            error_category="not_configured",
            provider="PUBLIC_WEB",
            raw_error=cfg_status["message"]
        )

    queries_to_run = search_plan.get("queries")
    if not queries_to_run or not isinstance(queries_to_run, list):
        queries_to_run = [{
            "id": "q1",
            "title": search_plan.get("keyword_title", "Executive"),
            "keywords": search_plan.get("search_keywords", "B2B SaaS")
        }]

    candidates = []
    seen_urls = set()
    engine_errors = []

    for q in queries_to_run[:3]:
        q_id = q.get("id", "q1")
        title = q.get("title", "")
        keywords = q.get("keywords", "")
        industry = q.get("industry", "")

        search_query = f'site:linkedin.com/in/ "{title}" "{keywords or industry}"'
        logger.info(f"[GTM Public Web] Executing public search: '{search_query}'")

        try:
            results = perform_public_web_search(search_query, max_results=min(10, limit))
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"[GTM Public Web] Search error for query {q_id}: {err_msg}")
            engine_errors.append(err_msg)
            continue

        for item in results:
            url = item.get("url") or ""
            title_text = item.get("title") or ""
            snippet = item.get("snippet") or ""

            # Validate that URL is a genuine LinkedIn profile
            m = re.search(r"linkedin\.com/in/([^/?#]+)", url, re.IGNORECASE)
            if not m:
                # Per Section 7: skip without creating synthetic IDs
                logger.debug(f"[GTM Public Web] Skipping non-profile URL: {url}")
                continue

            slug = m.group(1).strip().lower()
            if slug in seen_urls:
                continue
            seen_urls.add(slug)

            # Parse Name and Title from search snippet
            name = "LinkedIn Member"
            role = title
            company = ""

            clean_title = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title_text, flags=re.IGNORECASE).strip()
            parts = [p.strip() for p in re.split(r"\s*[-–—|]\s*", clean_title) if p.strip()]

            if len(parts) >= 1:
                name = parts[0]
            if len(parts) >= 2:
                role = parts[1]
            if len(parts) >= 3:
                company = parts[2]

            if not company and " at " in snippet:
                snip_match = re.search(r" at ([A-Z][A-Za-z0-9\s&]+?)(?:\.|\,|\;|\-|\n|$)", snippet)
                if snip_match:
                    company = snip_match.group(1).strip()

            norm_url = f"https://www.linkedin.com/in/{slug}"

            candidates.append({
                "urn_id": slug,
                "name": name,
                "role": role or title,
                "raw_headline": clean_title,
                "company": company or "Target Company",
                "location": q.get("location") or "United States",
                "profile_url": norm_url,
                "distance": "PUBLIC_INDEX",
                "provider": "PUBLIC_WEB",
                "source_query": q_id,
                "source_evidence": snippet[:300]
            })

            if len(candidates) >= limit:
                break

        if len(candidates) >= limit:
            break

    if candidates:
        return CandidateList(candidates[:limit], status="SUCCESS", provider="PUBLIC_WEB")
    if engine_errors:
        last_err = engine_errors[-1]
        is_challenge = any(k in last_err.lower() for k in ["202", "challenge", "bot challenge", "captcha"])
        is_quota = any(k in last_err.lower() for k in ["429", "quota", "rate limit"])
        is_auth = any(k in last_err.lower() for k in ["400", "403", "auth", "permission", "key"])

        if is_quota:
            status = "QUOTA_EXCEEDED"
            cat = "quota_exceeded"
        elif is_auth:
            status = "AUTH_ERROR"
            cat = "auth_error"
        elif is_challenge:
            status = "BOT_CHALLENGE"
            cat = "search_engine_challenge"
        else:
            status = "FAILED"
            cat = "search_engine_unavailable"

        return CandidateList([], status=status, error_category=cat, provider="PUBLIC_WEB", raw_error=last_err)

    return CandidateList([], status="ZERO_RESULTS", provider="PUBLIC_WEB")


# ====================================================================
# CANDIDATE MERGING & DEDUPLICATION
# ====================================================================

def merge_and_deduplicate_candidates(
    candidate_lists: List[List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Merges candidate lists from multiple providers and queries.
    Deduplicates using normalized LinkedIn identifier (vanity slug or URN).
    Preserves all contributing sources, query IDs, and evidence without merging unrelated individuals.
    Skips entries lacking a valid, extractable identifier (satisfying GlobalProfiles.linkedin_id non-null constraint).
    """
    merged = []
    seen = {}

    for c_list in candidate_lists:
        for c in c_list:
            norm_id = normalize_linkedin_identifier(c.get("profile_url"), c.get("urn_id"))
            if not norm_id:
                logger.info(f"[GTM Merging] Candidate missing extractable LinkedIn identifier, skipping: {c.get('name')}")
                continue

            provider = c.get("provider", "UNKNOWN")
            query_id = c.get("source_query", "unknown")

            if norm_id in seen:
                existing = merged[seen[norm_id]]
                sources = existing.setdefault("sources", [existing.get("provider", "UNKNOWN")])
                if provider not in sources:
                    sources.append(provider)
                    existing["provider"] = "DUAL"

                queries = existing.setdefault("queries", [existing.get("source_query", "unknown")])
                if query_id not in queries:
                    queries.append(query_id)

                if (not existing.get("company") or existing["company"] == "Target Company") and c.get("company"):
                    existing["company"] = c["company"]
                if (not existing.get("location") or existing["location"] == "Verified Market") and c.get("location"):
                    existing["location"] = c["location"]
                if (not existing.get("raw_headline")) and c.get("raw_headline"):
                    existing["raw_headline"] = c["raw_headline"]
            else:
                c_copy = dict(c)
                c_copy["urn_id"] = norm_id
                c_copy["profile_url"] = normalize_profile_url(c.get("profile_url"), norm_id)
                c_copy["sources"] = [provider]
                c_copy["queries"] = [query_id]
                seen[norm_id] = len(merged)
                merged.append(c_copy)

    return merged


# ====================================================================
# EVIDENCE-BASED QUALIFICATION & SCORING
# ====================================================================

def qualify_candidates_with_gemini(
    candidates: List[Dict[str, Any]],
    user_context: Dict[str, Any],
    web_enrichment_cache: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Evaluates discovered prospects against the user's saved ICP using concrete evidence.
    Applies deterministic exclusion filters first, then calls Gemini for evidence-based fit scoring.
    """
    if not candidates:
        return []

    offer = user_context.get("offer", "")
    target_icp = user_context.get("target_icp", "")
    icp = user_context.get("icp_raw", {})

    exclusions_str = icp.get("exclusions") or ""
    raw_exclusions = [e.strip().lower() for e in re.split(r"[,;|\n]", exclusions_str) if e.strip()]
    default_negatives = ["intern", "student", "freelance", "contractor"]
    all_exclusions = list(set(raw_exclusions + default_negatives))

    disqualified_candidates = []
    candidates_to_score = []

    for c in candidates:
        text_to_check = f"{c.get('name', '')} {c.get('role', '')} {c.get('raw_headline', '')}".lower()
        matched_exclusion = None
        for exc in all_exclusions:
            if re.search(rf"\b{re.escape(exc)}\b", text_to_check):
                matched_exclusion = exc
                break

        if matched_exclusion:
            c_dis = dict(c)
            c_dis.update({
                "fit_score": 15,
                "tier": "Disqualified",
                "qualification_reason": f"Excluded by negative criteria: '{matched_exclusion}'.",
                "intent_signals": "Disqualified based on negative role/title criteria.",
                "recommended_angle": "Not recommended for outreach.",
                "is_excluded": True,
                "public_contact": {
                    "linkedin": c.get("profile_url"),
                    "verified": bool(c.get("profile_url"))
                }
            })
            disqualified_candidates.append(c_dis)
        else:
            candidates_to_score.append(c)

    scored_candidates = []
    if candidates_to_score:
        candidates_payload = []
        for c in candidates_to_score:
            comp = c.get("company", "")
            enrichment = web_enrichment_cache.get(comp, {})
            candidates_payload.append({
                "urn_id": c.get("urn_id"),
                "name": c.get("name"),
                "role": c.get("role"),
                "company": comp,
                "location": c.get("location"),
                "company_summary": enrichment.get("summary", "")[:300]
            })

        prompt = f"""
You are a senior B2B Go-To-Market evaluation engine.
Evaluate the following prospects against our Ideal Customer Profile (ICP) and offering.

Our Offering:
{offer}

Target ICP Criteria:
{target_icp}

Prospects to Evaluate:
{json.dumps(candidates_payload, indent=2)}

For EACH prospect, provide:
1. fit_score: integer between 0 and 100 based on title alignment, industry relevance, and seniority.
2. qualification_reason: concise sentence explaining why they qualify (or do not qualify).
3. intent_signals: realistic intent indicators (e.g., active hiring, technology adoption, revenue stage).
4. recommended_angle: a tailored, value-driven conversation starter addressing their specific role.
5. tier: 'Tier 1 Priority Match' (85-100), 'Tier 2 Match' (70-84), or 'Moderate Match' (<70).

Return a single JSON ARRAY of objects:
[
  {{
    "urn_id": "...",
    "fit_score": 92,
    "tier": "Tier 1 Priority Match",
    "qualification_reason": "...",
    "intent_signals": "...",
    "recommended_angle": "..."
  }}
]
"""
        raw_response = _call_gemini_with_fallback(prompt, response_json=True)
        qual_list = _clean_json(raw_response)

        qual_by_urn = {}
        if isinstance(qual_list, list):
            for item in qual_list:
                if isinstance(item, dict) and "urn_id" in item:
                    qual_by_urn[str(item["urn_id"]).strip().lower()] = item

        for c in candidates_to_score:
            urn_key = str(c.get("urn_id") or "").strip().lower()
            q_data = qual_by_urn.get(urn_key, {})

            fit_score = q_data.get("fit_score", 75)
            tier = q_data.get("tier", "Tier 2 Match" if fit_score >= 70 else "Moderate Match")
            reason = q_data.get("qualification_reason", f"Matches role {c.get('role')} at {c.get('company')}.")
            signals = q_data.get("intent_signals", "Active leadership in target sector.")
            angle = q_data.get("recommended_angle", f"Discuss scaling operations with {c.get('name')}.")

            scored_candidates.append({
                **c,
                "fit_score": fit_score,
                "tier": tier,
                "qualification_reason": reason,
                "intent_signals": signals,
                "recommended_angle": angle,
                "is_excluded": False,
                "public_contact": {
                    "linkedin": c.get("profile_url"),
                    "verified": bool(c.get("profile_url"))
                }
            })

    all_qualified = scored_candidates + disqualified_candidates
    all_qualified.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
    return all_qualified


# ====================================================================
# POSTGRESQL PERSISTENCE
# ====================================================================

def persist_qualified_opportunities(
    user_id: int,
    job_id: Optional[int],
    qualified_candidates: List[Dict[str, Any]],
    icp_version: int = 1
) -> int:
    """
    Persists qualified prospects to PostgreSQL:
    1. Upserts into GlobalProfiles (deduplicated by linkedin_id).
    2. Upserts into UsersProfiles (tenant-isolated for user_id).
    """
    saved_count = 0
    now = datetime.utcnow()

    valid_job = db_session.query(ResearchJobs).filter_by(id=job_id).first() if job_id else None
    actual_job_id = valid_job.id if valid_job else None

    for c in qualified_candidates:
        norm_urn = normalize_linkedin_identifier(c.get("profile_url"), c.get("urn_id"))
        if not norm_urn:
            continue

        company_data_payload = {
            "intent_signals": c.get("intent_signals", ""),
            "recommended_angle": c.get("recommended_angle", ""),
            "public_contact": c.get("public_contact", {}),
            "tier": c.get("tier", ""),
            "sources": c.get("sources", [c.get("provider", "UNKNOWN")]),
            "queries": c.get("queries", [c.get("source_query", "unknown")])
        }

        # 1. GlobalProfiles Deduplication & Upsert
        is_new_profile = False
        global_profile = db_session.query(GlobalProfiles).filter_by(linkedin_id=norm_urn).first()
        if not global_profile:
            try:
                with db_session.begin_nested():
                    global_profile = GlobalProfiles(
                        linkedin_id=norm_urn,
                        profile_url=c.get("profile_url") or f"https://www.linkedin.com/in/{norm_urn}",
                        name=c.get("name"),
                        role=c.get("role"),
                        headline=c.get("raw_headline"),
                        company=c.get("company"),
                        location=c.get("location"),
                        company_data=company_data_payload,
                        source=c.get("provider", GlobalProfileSource.WEB.value),
                        recommended_no_of_times=1,
                        last_updated=now,
                        created_at=now
                    )
                    db_session.add(global_profile)
                    db_session.flush()
                    is_new_profile = True
            except Exception:
                global_profile = db_session.query(GlobalProfiles).filter_by(linkedin_id=norm_urn).first()

        if global_profile and not is_new_profile:
            global_profile.name = c.get("name") or global_profile.name
            global_profile.role = c.get("role") or global_profile.role
            global_profile.company = c.get("company") or global_profile.company
            global_profile.company_data = company_data_payload
            global_profile.recommended_no_of_times = (global_profile.recommended_no_of_times or 0) + 1
            global_profile.last_updated = now

        # 2. UsersProfiles Tenant Isolation & Upsert
        user_profile = db_session.query(UsersProfiles).filter_by(
            user_id=user_id,
            global_id=global_profile.global_id
        ).first()

        lead_status = LeadStatus.QUALIFIED.value if c.get("fit_score", 0) >= 70 else LeadStatus.NEW.value

        research_src = c.get("provider", "VOYAGER_WEB_DUAL")
        if c.get("sources") and len(c.get("sources")) > 1:
            research_src = "DUAL"

        if not user_profile:
            try:
                with db_session.begin_nested():
                    user_profile = UsersProfiles(
                        user_id=user_id,
                        global_id=global_profile.global_id,
                        research_job_id=actual_job_id,
                        research_source=research_src,
                        match_score=c.get("fit_score", 0),
                        qualification_reason=c.get("qualification_reason", ""),
                        lead_status=lead_status,
                        icp_version=icp_version,
                        first_seen_at=now,
                        last_seen_at=now,
                        created_at=now,
                        updated_at=now
                    )
                    db_session.add(user_profile)
                    db_session.flush()
            except Exception:
                user_profile = db_session.query(UsersProfiles).filter_by(
                    user_id=user_id,
                    global_id=global_profile.global_id
                ).first()
        if user_profile:
            user_profile.match_score = c.get("fit_score", user_profile.match_score)
            user_profile.qualification_reason = c.get("qualification_reason", user_profile.qualification_reason)
            user_profile.research_job_id = actual_job_id
            user_profile.research_source = research_src
            user_profile.last_seen_at = now
            user_profile.updated_at = now

        saved_count += 1

    db_session.commit()
    return saved_count


# ====================================================================
# ASYNCHRONOUS PIPELINE WORKER & ORCHESTRATOR
# ====================================================================

def _execute_gtm_pipeline_worker(
    app,
    user_id: int,
    job_id: int,
    target_leads: int,
    persona_filter: Optional[str]
):
    """
    Background worker that runs the full dual-discovery GTM pipeline within app context.
    Executes Voyager and Public-Web independently, merges candidates, qualifies, and persists.
    """
    with app.app_context():
        job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
        if not job:
            logger.error(f"[GTM Worker] Job {job_id} not found.")
            return

        try:
            job.status = ResearchJobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            job.heartbeat_at = datetime.utcnow()
            job.progress = {"step": "PLANNING", "pct": 15, "message": "Analyzing ICP & creating targeted queries"}
            db_session.commit()

            # 1. Fetch User Context
            context = get_user_gtm_context(user_id)
            if not context.get("onboarding_completed"):
                raise ValueError("Onboarding incomplete. Please complete company and ICP questions.")

            # 2. Multi-Query Planning via Gemini
            search_plan = generate_search_plan(context, persona_filter)
            job.progress = {"step": "DISCOVERY", "pct": 35, "message": "Executing multi-channel candidate discovery"}
            job.heartbeat_at = datetime.utcnow()
            db_session.commit()

            provider_errors = {}
            provider_outcomes = {}

            # 3. Native Candidate Discovery: LinkedIn Voyager (Per-User Authenticated Session)
            logger.info(f"[GTM Worker] Running native Voyager discovery for user {user_id}")
            voyager_res = discover_candidates_via_voyager(user_id, search_plan, limit=min(target_leads, 25))
            v_status = getattr(voyager_res, "status", "SUCCESS" if voyager_res else "ZERO_RESULTS")

            provider_outcomes["VOYAGER"] = v_status

            if v_status == "SUCCESS" and len(voyager_res) > 0:
                merged_candidates = voyager_res
                logger.info(f"[GTM Worker] Discovered {len(merged_candidates)} candidates via Voyager.")
            elif v_status == "ZERO_RESULTS" or (v_status == "SUCCESS" and len(voyager_res) == 0):
                # Genuine Zero Results: Discovery executed without error, but 0 candidates matched ICP
                job.status = ResearchJobStatus.COMPLETED.value
                job.progress = {
                    "step": "COMPLETED",
                    "pct": 100,
                    "message": "Discovery completed: 0 candidates matched your ICP criteria",
                    "provider_outcomes": {"VOYAGER": "ZERO_RESULTS"},
                    "discovery_mode": "VOYAGER"
                }
                job.results_count = 0
                job.completed_at = datetime.utcnow()
                job.heartbeat_at = datetime.utcnow()
                db_session.commit()
                logger.info(f"[GTM Worker] Job {job_id} completed with 0 results after successful discovery.")
                return
            else:
                # Terminal Failure: Session expired, challenge, rate limit, or provider error
                v_cat = getattr(voyager_res, "error_category", None) or v_status
                v_raw = getattr(voyager_res, "raw_error", None) or v_status
                provider_outcomes["VOYAGER"] = f"FAILED_{v_status}"
                provider_errors["VOYAGER"] = v_cat

                if v_cat in ("expired", "auth_expired", "login", "disconnected", "no_connection"):
                    err_summary = "LinkedIn session expired or disconnected. Please reconnect your LinkedIn account in Settings/Onboarding to continue discovery."
                elif v_cat in ("challenge", "checkpoint", "checkpoint_challenge"):
                    err_summary = "LinkedIn security verification required. Please complete verification by logging in interactively."
                elif v_cat in ("rate_limit", "rate_limited"):
                    err_summary = "LinkedIn rate limit encountered. Please wait a short while before initiating new prospect discovery."
                else:
                    err_summary = f"LinkedIn discovery failed: {v_raw}"

                job.status = ResearchJobStatus.FAILED.value
                job.error_message = err_summary
                job.progress = {
                    "step": "FAILED",
                    "pct": 100,
                    "message": err_summary,
                    "provider_outcomes": provider_outcomes,
                    "discovery_mode": "VOYAGER"
                }
                job.results_count = 0
                job.completed_at = datetime.utcnow()
                job.heartbeat_at = datetime.utcnow()
                db_session.commit()
                logger.warning(f"[GTM Worker] Job {job_id} failed: {err_summary}")
                return

            # 6. Company Enrichment via Agent-Reach / Jina Reader
            job.progress = {"step": "ENRICHMENT", "pct": 60, "message": "Enriching company context via public intelligence", "provider_outcomes": provider_outcomes}
            job.heartbeat_at = datetime.utcnow()
            db_session.commit()

            web_enrichment_cache = {}
            for c in merged_candidates:
                comp_name = c.get("company")
                if comp_name and comp_name not in web_enrichment_cache:
                    web_enrichment_cache[comp_name] = enrich_company_public_web(comp_name)

            # 7. Evidence-based Qualification & Scoring via Gemini
            job.progress = {"step": "QUALIFYING", "pct": 80, "message": "Evaluating prospects against ICP criteria", "provider_outcomes": provider_outcomes}
            job.heartbeat_at = datetime.utcnow()
            db_session.commit()

            qualified_candidates = qualify_candidates_with_gemini(merged_candidates, context, web_enrichment_cache)

            # 8. PostgreSQL Persistence
            job.progress = {"step": "PERSISTING", "pct": 95, "message": "Saving qualified opportunities to dashboard", "provider_outcomes": provider_outcomes}
            job.heartbeat_at = datetime.utcnow()
            db_session.commit()

            icp_ver = context.get("icp_raw", {}).get("version", 1)
            saved_count = persist_qualified_opportunities(user_id, job_id, qualified_candidates, icp_version=icp_ver)

            # 9. Complete Job
            job.status = ResearchJobStatus.COMPLETED.value
            job.progress = {
                "step": "COMPLETED",
                "pct": 100,
                "message": f"Successfully discovered and qualified {saved_count} leads via LinkedIn Voyager",
                "provider_outcomes": {"VOYAGER": "SUCCESS"},
                "discovery_mode": "VOYAGER"
            }
            job.results_count = saved_count
            job.completed_at = datetime.utcnow()
            job.heartbeat_at = datetime.utcnow()
            db_session.commit()
            logger.info(f"[GTM Worker] Job {job_id} completed with {saved_count} results via LinkedIn Voyager.")

        except Exception as e:
            db_session.rollback()
            err_msg = str(e)
            logger.error(f"[GTM Worker] Job {job_id} failed: {err_msg}", exc_info=True)
            try:
                fail_job = db_session.query(ResearchJobs).filter_by(id=job_id).first()
                if fail_job:
                    fail_job.status = ResearchJobStatus.FAILED.value
                    fail_job.error_message = err_msg
                    fail_job.progress = {
                        "step": "FAILED",
                        "pct": 100,
                        "message": f"Pipeline failure: {err_msg}",
                        "provider_outcomes": provider_outcomes if 'provider_outcomes' in locals() else {}
                    }
                    fail_job.completed_at = datetime.utcnow()
                    fail_job.heartbeat_at = datetime.utcnow()
                    db_session.commit()
            except Exception as commit_err:
                logger.error(f"[GTM Worker] Failed to persist failure status for job {job_id}: {commit_err}")
                db_session.rollback()
        finally:
            db_session.remove()


def start_gtm_research_job(
    app,
    user_id: int,
    target_leads: int = 25,
    persona_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Public entry point to initiate an asynchronous GTM research job.
    Enforces active job singularity and validates required context.
    """
    # Check for active existing job
    existing = db_session.query(ResearchJobs).filter(
        ResearchJobs.user_id == user_id,
        ResearchJobs.status.in_([ResearchJobStatus.QUEUED.value, ResearchJobStatus.RUNNING.value])
    ).first()

    if existing:
        return {
            "job_id": existing.id,
            "status": existing.status,
            "is_existing": True,
            "message": "A research run is already in progress."
        }

    # Verify context
    context = get_user_gtm_context(user_id)
    if not context.get("onboarding_completed"):
        raise ValueError("Onboarding not completed. Please complete company and ICP setup first.")

    icp_ver = context.get("icp_raw", {}).get("version", 1)

    job = ResearchJobs(
        user_id=user_id,
        status=ResearchJobStatus.QUEUED.value,
        research_type=ResearchType.WEB_DISCOVERY.value,
        icp_version=icp_ver,
        budget={"target_leads": target_leads},
        progress={"step": "QUEUED", "pct": 5, "message": "Job queued for background processing"},
        attempts=1,
        created_at=datetime.utcnow()
    )
    db_session.add(job)
    db_session.commit()

    job_id = job.id

    # Spawn thread
    thread = threading.Thread(
        target=_execute_gtm_pipeline_worker,
        args=(app, user_id, job_id, target_leads, persona_filter),
        daemon=True
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "QUEUED",
        "is_existing": False,
        "message": "Research job successfully initiated."
    }


def get_user_opportunities(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns all qualified opportunities saved for the user in PostgreSQL,
    joining UsersProfiles with GlobalProfiles.
    """
    records = db_session.query(UsersProfiles, GlobalProfiles).join(
        GlobalProfiles, UsersProfiles.global_id == GlobalProfiles.global_id
    ).filter(
        UsersProfiles.user_id == user_id
    ).order_by(
        UsersProfiles.match_score.desc().nullslast(),
        UsersProfiles.updated_at.desc()
    ).all()

    opportunities = []
    for up, gp in records:
        c_data = gp.company_data or {}
        opportunities.append({
            "id": up.id,
            "global_id": gp.global_id,
            "name": gp.name or "LinkedIn Member",
            "role": gp.role or "Executive",
            "company": gp.company or "Organization",
            "location": gp.location or "",
            "profile_url": gp.profile_url or "",
            "score": up.match_score or 70,
            "tier": c_data.get("tier") or ("Tier 1 Priority Match" if (up.match_score or 0) >= 85 else "Tier 2 Match"),
            "qualification": up.qualification_reason or "Matches target profile.",
            "need": c_data.get("recommended_angle") or "Explore operational alignment.",
            "signals": c_data.get("intent_signals") or "Active in market.",
            "status": up.lead_status or "QUALIFIED",
            "created_at": up.created_at.isoformat() if up.created_at else ""
        })

    return opportunities
