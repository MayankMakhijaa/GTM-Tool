"""
Google Places API Rating Fallback Service
Provides conservative, last-resort company rating resolution using Google Places API.
Used only when all primary public review sources (Justdial, AmbitionBox, GoodFirms,
Sulekha, Clutch, Trustpilot) have been exhausted without finding a verified rating.
"""
import re
import os
import logging
from typing import Dict, Any, Optional, Tuple, List, Set
from datetime import datetime, timezone

import requests
from config import Config
from app.services.company_discovery_service import get_root_domain

logger = logging.getLogger(__name__)

STOP_COMPANY_WORDS: Set[str] = {
    "pvt", "ltd", "private", "limited", "inc", "incorporated", "llc", "corp",
    "corporation", "co", "technologies", "solutions", "services", "group", "holdings",
    "pte"
}

# Businesses/categories that indicate an unrelated consumer/retail business
UNRELATED_BUSINESS_KEYWORDS: Set[str] = {
    "dance", "academy", "salon", "spa", "restaurant", "hotel", "hospital",
    "clinic", "gym", "fitness", "bakery", "cafe", "bar", "catering",
    "school", "college", "university", "institute", "jewellers", "optical",
    "motors", "auto", "travels", "tours", "realtors", "properties"
}


def get_iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_company_tokens(name: str) -> List[str]:
    """Extracts distinctive meaningful tokens from a company name."""
    cleaned = re.sub(r'[^\w\s]', ' ', (name or "").lower())
    return [t for t in cleaned.split() if t not in STOP_COMPANY_WORDS and len(t) > 1]


def match_google_place_candidate(
    candidate: Dict[str, Any],
    company_name: str,
    website_url: str = "",
    location: Optional[str] = None
) -> bool:
    """
    Conservatively validates whether a Google Places candidate matches the target company.
    Rejects candidates with mismatched names, conflicting locations, or unrelated business categories.
    Does NOT match if candidate lacks a valid rating.
    """
    # 1. Rating validation: candidate MUST have a valid numeric rating
    rating = candidate.get("rating")
    if rating is None:
        return False
    try:
        f_rating = float(rating)
        if f_rating < 1.0 or f_rating > 5.0:
            return False
    except (ValueError, TypeError):
        return False

    candidate_name = (candidate.get("name") or "").strip()
    if not candidate_name:
        return False

    target_tokens = clean_company_tokens(company_name)
    cand_tokens = clean_company_tokens(candidate_name)

    if not target_tokens or not cand_tokens:
        return False

    target_tokens_set = set(target_tokens)
    cand_tokens_set = set(cand_tokens)

    # 2. Check for unrelated category keywords in candidate name (e.g. "Fame Dance Academy" vs "Fameweb")
    extra_tokens = cand_tokens_set - target_tokens_set
    if extra_tokens & UNRELATED_BUSINESS_KEYWORDS:
        # Candidate has an unrelated retail/entertainment category not present in target
        return False

    # 3. Core brand token match
    target_clean = " ".join(target_tokens)
    cand_clean = " ".join(cand_tokens)

    name_matched = False
    if target_clean == cand_clean:
        name_matched = True
    elif target_tokens_set.issubset(cand_tokens_set):
        # Candidate contains all target tokens (e.g. "Fameweb Technologies" for "Fameweb")
        if len(cand_tokens) <= len(target_tokens) + 2:
            name_matched = True
    elif len(target_tokens) > 1:
        # Multi-token overlap: at least 75% of target tokens match
        overlap = len(target_tokens_set & cand_tokens_set)
        if overlap / len(target_tokens) >= 0.75:
            name_matched = True

    if not name_matched:
        return False

    # 4. Location consistency check if location is provided
    if location and len(location.strip()) > 2:
        loc_clean = re.sub(r'[^\w\s]', ' ', location.lower())
        loc_tokens = [tok for tok in loc_clean.split() if len(tok) > 2]
        addr_lower = (candidate.get("formatted_address") or "").lower()

        if addr_lower and loc_tokens:
            has_loc_overlap = any(tok in addr_lower for tok in loc_tokens)
            if extra_tokens and not has_loc_overlap:
                return False

    return True


def is_google_places_api_configured() -> bool:
    """Checks whether a valid non-placeholder Google Maps / Places API key is configured."""
    api_key = (
        getattr(Config, "GOOGLE_MAPS_API_KEY", None)
        or getattr(Config, "GOOGLE_PLACES_API_KEY", None)
        or os.environ.get("GOOGLE_MAPS_API_KEY")
        or os.environ.get("GOOGLE_PLACES_API_KEY")
    )
    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        return False
    key_lower = api_key.lower()
    if "your_" in key_lower or "placeholder" in key_lower:
        return False
    return True


def lookup_google_places_rating(
    company_name: str,
    website_url: str = "",
    location: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
    """
    Queries Google Places Text Search API as a last-resort fallback for company rating.
    Returns: (res_map, status, diagnostic)
      res_map: {"rating": rating_item} if status == "VERIFIED", else None
      status: "VERIFIED" | "NOT_FOUND" | "UNCONFIGURED" | "SEARCH_UNAVAILABLE"
      diagnostic: dict with metadata
    """
    company_name = (company_name or "").strip()
    if not company_name:
        return None, "NOT_FOUND", {"attempted": False, "reason": "Empty company_name"}

    if not is_google_places_api_configured():
        logger.debug("Google Places API key is not configured; skipping Google Places fallback.")
        return None, "UNCONFIGURED", {"attempted": False, "reason": "Missing GOOGLE_MAPS_API_KEY"}

    api_key = (
        getattr(Config, "GOOGLE_MAPS_API_KEY", None)
        or getattr(Config, "GOOGLE_PLACES_API_KEY", None)
        or os.environ.get("GOOGLE_MAPS_API_KEY")
        or os.environ.get("GOOGLE_PLACES_API_KEY")
    )

    # Formulate query: prefer company name + location context when available
    if location and len(location.strip()) > 2:
        query = f"{company_name} {location.strip()}"
    else:
        query = company_name

    endpoint = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": api_key
    }

    diag: Dict[str, Any] = {
        "attempted": True,
        "query": query,
        "candidates_count": 0
    }

    try:
        resp = requests.get(endpoint, params=params, timeout=5.0)
    except Exception as err:
        logger.warning(f"Google Places API request failed: {type(err).__name__}")
        diag["error"] = f"Network error: {type(err).__name__}"
        return None, "SEARCH_UNAVAILABLE", diag

    if resp.status_code != 200:
        logger.warning(f"Google Places API returned HTTP {resp.status_code}")
        diag["error"] = f"HTTP {resp.status_code}"
        return None, "SEARCH_UNAVAILABLE", diag

    try:
        data = resp.json()
    except Exception as err:
        logger.warning(f"Failed to parse Google Places JSON response: {err}")
        diag["error"] = "Invalid JSON response"
        return None, "SEARCH_UNAVAILABLE", diag

    api_status = data.get("status")
    if api_status in ("REQUEST_DENIED", "OVER_QUERY_LIMIT", "UNKNOWN_ERROR"):
        err_msg = data.get("error_message") or api_status
        logger.warning(f"Google Places API returned status {api_status}: {err_msg}")
        diag["error"] = f"{api_status}: {err_msg}"
        return None, "SEARCH_UNAVAILABLE", diag

    if api_status == "ZERO_RESULTS" or not data.get("results"):
        diag["reason"] = "ZERO_RESULTS"
        return None, "NOT_FOUND", diag

    if api_status != "OK":
        diag["error"] = f"API status: {api_status}"
        return None, "SEARCH_UNAVAILABLE", diag

    candidates = data.get("results") or []
    diag["candidates_count"] = len(candidates)

    # Evaluate candidates with conservative matching
    for cand in candidates:
        if match_google_place_candidate(cand, company_name, website_url, location):
            score = float(cand["rating"])
            user_ratings_total = cand.get("user_ratings_total")
            review_count = int(user_ratings_total) if user_ratings_total else None

            review_str = f" ({review_count} reviews on Google Maps)" if review_count else " (Google Maps)"
            formatted_val = f"{score:.1f} / 5{review_str}"

            place_id = cand.get("place_id") or ""
            source_url = (
                f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                if place_id else "https://maps.google.com"
            )
            evidence = (
                f"Google Places verified rating: {score:.1f}/5"
                + (f" across {review_count} reviews" if review_count else "")
            )

            rating_item = {
                "value": formatted_val,
                "score": score,
                "max_rating": 5.0,
                "review_count": review_count,
                "source_name": "Google Places",
                "source_url": source_url,
                "evidence": evidence,
                "retrieval_timestamp": get_iso_timestamp(),
                "verification_status": "VERIFIED"
            }
            diag["matched_place"] = {
                "name": cand.get("name"),
                "place_id": place_id,
                "formatted_address": cand.get("formatted_address")
            }
            return {"rating": rating_item}, "VERIFIED", diag

    diag["reason"] = "No confident candidate match with rating"
    return None, "NOT_FOUND", diag
