import os
import json
import time
import sqlite3
import urllib.request
import urllib.parse
import urllib.error
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from google import genai

DB_PATH = os.path.join(os.getcwd(), "gtm_opportunities.db")
GTM_MODEL = "gemini-3.5-flash"


def init_db():
    """Initializes the SQLite database table 'opportunities' if not exists."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            website TEXT,
            location TEXT,
            industry TEXT,
            company_size TEXT,
            description TEXT,
            signals TEXT,
            evidence TEXT,
            icp_fit_score INTEGER DEFAULT 0,
            intent_score INTEGER DEFAULT 0,
            timing_score INTEGER DEFAULT 0,
            overall_score INTEGER DEFAULT 0,
            why_now TEXT,
            recommended_action TEXT,
            reason TEXT,
            confidence TEXT,
            created_at TEXT
        );
    """)
    conn.commit()
    conn.close()


def save_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inserts analyzed opportunities into the SQLite opportunities table."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = []
    now_iso = datetime.now().isoformat()

    for opp in opportunities:
        company_name = str(opp.get("company_name") or "Unknown Company").strip()
        website = str(opp.get("website") or "").strip()
        location = str(opp.get("location") or "").strip()
        industry = str(opp.get("industry") or "").strip()
        company_size = str(opp.get("company_size") or "").strip()
        description = str(opp.get("description") or "").strip()

        signals = json.dumps(opp.get("signals") or [])
        evidence = json.dumps(opp.get("evidence") or [])

        icp_fit_score = int(opp.get("icp_fit_score", 0) or 0)
        intent_score = int(opp.get("intent_score", 0) or 0)
        timing_score = int(opp.get("timing_score", 0) or 0)
        overall_score = int(opp.get("overall_score", 0) or 0)

        why_now = str(opp.get("why_now") or "Insufficient evidence of a current trigger.").strip()
        recommended_action = str(opp.get("recommended_action") or "Research company leadership.").strip()
        reason = str(opp.get("reason") or "").strip()
        confidence = str(opp.get("confidence") or "medium").strip()

        cursor.execute("""
            INSERT INTO opportunities (
                company_name, website, location, industry, company_size, description,
                signals, evidence, icp_fit_score, intent_score, timing_score,
                overall_score, why_now, recommended_action, reason, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_name, website, location, industry, company_size, description,
            signals, evidence, icp_fit_score, intent_score, timing_score,
            overall_score, why_now, recommended_action, reason, confidence, now_iso
        ))
        row_id = cursor.lastrowid

        opp_copy = dict(opp)
        opp_copy["id"] = row_id
        opp_copy["created_at"] = now_iso
        saved.append(opp_copy)

    conn.commit()
    conn.close()
    return saved


def get_all_opportunities() -> List[Dict[str, Any]]:
    """Retrieves all stored opportunities from SQLite ordered by overall_score descending."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opportunities ORDER BY overall_score DESC, id DESC")
    rows = cursor.fetchall()
    results = []
    for r in rows:
        item = dict(r)
        try:
            item["signals"] = json.loads(item["signals"]) if item["signals"] else []
        except Exception:
            item["signals"] = []
        try:
            item["evidence"] = json.loads(item["evidence"]) if item["evidence"] else []
        except Exception:
            item["evidence"] = []
        results.append(item)
    conn.close()
    return results


def _get_gemini_client() -> genai.Client:
    """Returns an authenticated genai.Client using GEMINI_API_KEY."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment.")
    return genai.Client(api_key=api_key)


def _call_interactions_with_retry(client: genai.Client, **kwargs) -> Any:
    """Helper to execute client.interactions.create."""
    return client.interactions.create(**kwargs)


def _extract_text_from_interaction(res: Any) -> str:
    """Safely extracts text output from an Interaction response."""
    output_text = getattr(res, "output_text", None) or getattr(res, "text", None)
    if output_text and isinstance(output_text, str):
        return output_text

    steps = getattr(res, "steps", []) or []
    collected = []
    for step in steps:
        step_type = getattr(step, "type", None) or (step.get("type") if isinstance(step, dict) else None)
        if step_type == "model_output":
            content = getattr(step, "content", None) or (step.get("content") if isinstance(step, dict) else None)
            if isinstance(content, list):
                for item in content:
                    item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                    if item_type == "text":
                        text_val = getattr(item, "text", None) or (item.get("text") if isinstance(item, dict) else None)
                        if isinstance(text_val, str):
                            collected.append(text_val)
    return "".join(collected)


def _clean_json_markdown(raw_text: str) -> str:
    """Strips ```json ... ``` markdown fence lines if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# Optional helper for standard HTTP page fetching (no scrapers/bypasses)
def fetch_public_page_snippet(url: str) -> Optional[str]:
    """
    Fetches a public web page using standard urllib.request with strict 5s timeout.
    Safely skips if request is blocked or fails.
    """
    if not url or not url.startswith("http"):
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WebCheck/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                html = resp.read().decode("utf-8", errors="ignore")
                text = " ".join(html.split())
                return text[:1000]
    except Exception:
        pass
    return None


# ====================================================================
# STEP 1: LOCAL PYTHON QUERY GENERATION (NO GEMINI)
# ====================================================================
def generate_local_search_queries(offer: str, target_icp: str, additional_context: str = "") -> List[str]:
    """
    Deterministically constructs dynamic search query variations from user Offer and ICP text.
    Zero Gemini calls in this step.
    """
    clean_icp = target_icp.strip()
    clean_offer = offer.strip()
    clean_context = additional_context.strip()

    queries = []

    # Variation 1: Direct target ICP + Offer focus
    queries.append(f"{clean_icp} {clean_offer}".strip())

    # Variation 2: Growth / Expansion / Hiring signals
    queries.append(f"{clean_icp} hiring OR expansion OR growing".strip())

    # Variation 3: Operational pain points or software tools
    queries.append(f"{clean_icp} operational complexity OR software OR platform".strip())

    if clean_context:
        # Variation 4: Additional context direction
        queries.append(f"{clean_icp} {clean_context}".strip())

    # Truncate overly long query strings cleanly
    formatted_queries = []
    for q in queries:
        q_str = " ".join(q.split())
        if q_str and q_str not in formatted_queries:
            formatted_queries.append(q_str[:160])

    return formatted_queries[:4]


# ====================================================================
# STEP 2 & 3: DIRECT SEARCH API DATA COLLECTION (BING / GOOGLE CSE)
# ====================================================================
def _search_bing(query: str, api_key: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """Executes search query via Bing Web Search API."""
    if not query or not api_key:
        return []
    url = f"https://api.bing.microsoft.com/v7.0/search?q={urllib.parse.quote(query)}&count={num_results}"
    req = urllib.request.Request(
        url,
        headers={
            "Ocp-Apim-Subscription-Key": api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2B-GTM-Agent/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                pages = data.get("webPages", {}).get("value", [])
                out = []
                for p in pages:
                    out.append({
                        "query": query,
                        "source": "Bing Web Search API",
                        "title": p.get("name", "Search Result"),
                        "url": p.get("url", ""),
                        "snippet": p.get("snippet", "")
                    })
                return out
    except Exception as e:
        print(f"[GTM ENGINE] Bing Search Error for query '{query}': {e}")
    return []


def _search_google_custom(query: str, api_key: str, cx: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """Executes search query via Google Custom Search JSON API."""
    if not query or not api_key or not cx:
        return []
    url = f"https://customsearch.googleapis.com/v1?key={api_key}&cx={cx}&q={urllib.parse.quote(query)}&num={num_results}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2B-GTM-Agent/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])
                out = []
                for item in items:
                    out.append({
                        "query": query,
                        "source": "Google Custom Search API",
                        "title": item.get("title", "Search Result"),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    })
                return out
    except Exception as e:
        print(f"[GTM ENGINE] Google CSE Error for query '{query}': {e}")
    return []


def execute_direct_search_apis(queries: List[str]) -> Tuple[List[Dict[str, Any]], str]:
    """
    Executes queries via Bing Web Search API (Primary) or Google Custom Search API (Fallback).
    Throws ValueError if no search API credentials are configured in environment.
    """
    bing_key = os.environ.get("BING_SEARCH_API_KEY") or os.environ.get("BING_API_KEY")
    google_key = os.environ.get("GOOGLE_SEARCH_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CSE_ID") or os.environ.get("GOOGLE_SEARCH_ENGINE_ID") or os.environ.get("GOOGLE_CX")

    results = []
    engine_used = None

    if bing_key:
        engine_used = "Bing Web Search API"
        for q in queries:
            results.extend(_search_bing(q, bing_key, num_results=5))
    elif google_key and google_cx:
        engine_used = "Google Custom Search JSON API"
        for q in queries:
            results.extend(_search_google_custom(q, google_key, google_cx, num_results=5))
    else:
        raise ValueError(
            "Search API credentials not configured. Please set BING_SEARCH_API_KEY (or GOOGLE_SEARCH_API_KEY and GOOGLE_CSE_ID) in environment."
        )

    return results, engine_used


# ====================================================================
# STEP 4: PUBLIC EVIDENCE COLLECTION & CANDIDATE NORMALIZATION
# ====================================================================
def normalize_search_results_into_candidates(search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Groups raw search results by domain/company and normalizes into up to 10 candidate company objects.
    Performs safe public page fetching for evidence snippets.
    """
    candidates_map = {}

    for item in search_results:
        url = item.get("url") or ""
        title = item.get("title") or ""
        snippet = item.get("snippet") or ""

        if not url or not url.startswith("http"):
            continue

        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.replace("www.", "").strip().lower()
        if not domain or "bing.com" in domain or "google.com" in domain:
            continue

        # Clean company name candidate
        company_name = title.split("-")[0].split("|")[0].split(":")[0].strip()
        if not company_name or len(company_name) < 2:
            company_name = domain.split(".")[0].capitalize()

        if domain not in candidates_map:
            page_text = fetch_public_page_snippet(url) or ""

            candidates_map[domain] = {
                "company_name": company_name,
                "website": f"{parsed.scheme}://{parsed.netloc}",
                "location": "Location from public web profile",
                "industry": "Industry from web profile",
                "company_size": "Company size from web profile",
                "description": snippet or f"Discovered via web search at {domain}",
                "signals": ["Public Web Signal"],
                "evidence_snippets": [
                    {
                        "signal": "Search Signal",
                        "snippet": snippet or page_text[:250],
                        "source_url": url,
                        "source_title": title,
                        "page_text": page_text[:500] if page_text else None
                    }
                ]
            }
        else:
            if len(candidates_map[domain]["evidence_snippets"]) < 3:
                candidates_map[domain]["evidence_snippets"].append({
                    "signal": "Web Evidence",
                    "snippet": snippet,
                    "source_url": url,
                    "source_title": title,
                    "page_text": None
                })

    candidates = list(candidates_map.values())
    return candidates[:10]


# ====================================================================
# STEP 5: GEMINI BATCH OPPORTUNITY ANALYZER (1 SINGLE GEMINI CALL)
# ====================================================================
def batch_analyze_opportunities(offer: str, target_icp: str, additional_context: str, candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Call #1 & ONLY Gemini Call: Sends collected candidates + evidence to Gemini Interactions API
    (gemini-3.6-flash) in ONE single batch analysis request to evaluate ICP fit, intent, timing,
    'Why Now?' rationale, and recommended actions.
    """
    if not candidates:
        return [], "", ""

    client = _get_gemini_client()
    candidates_json = json.dumps(candidates, indent=2)

    prompt = f"""
You are an elite B2B Go-To-Market Analyst.
Evaluate the following candidate companies against the user's Offer & ICP in ONE BATCH analysis.

USER OFFER:
{offer}

TARGET ICP:
{target_icp}

ADDITIONAL CONTEXT:
{additional_context}

COLLECTED CANDIDATES & PUBLIC EVIDENCE:
{candidates_json}

EVALUATION RULES:
1. Analyze each company strictly based on the supplied public evidence.
2. DO NOT invent funding events, hiring activity, expansion, revenue, or business problems not present in the evidence.
3. If evidence of a timing trigger is lacking, set why_now to "Insufficient evidence of a current trigger." and set confidence to "low".
4. Calculate integer scores (0-100) for: icp_fit_score, intent_score, timing_score, overall_score.
5. Provide a clear, actionable recommended_action (e.g., "Research Founder and outreach regarding operational automation.").

Return a SINGLE valid JSON array matching this exact schema:

[
  {{
    "company_name": "Exact Name matching candidate",
    "website": "https://...",
    "location": "City, State",
    "industry": "Industry",
    "company_size": "Size",
    "description": "Company overview",
    "icp_fit_score": 85,
    "intent_score": 75,
    "timing_score": 80,
    "overall_score": 80,
    "why_now": "Explanation referencing actual evidence.",
    "reason": "Brief summary of evaluation.",
    "recommended_action": "Suggested next step.",
    "confidence": "high" | "medium" | "low",
    "signals": ["Public Signal 1", "Public Signal 2"],
    "evidence": [
      {{
        "signal": "Web Evidence",
        "description": "Detail from collected snippet",
        "source_url": "https://...",
        "source_title": "Page title"
      }}
    ]
  }}
]
"""

    res = _call_interactions_with_retry(
        client,
        model=GTM_MODEL,
        input=prompt
    )

    raw_text = _extract_text_from_interaction(res)
    if not raw_text:
        raise ValueError("Gemini Batch Analysis returned an empty response.")

    clean_text = _clean_json_markdown(raw_text)

    try:
        analyzed = json.loads(clean_text)
        if isinstance(analyzed, dict) and "opportunities" in analyzed:
            analyzed = analyzed["opportunities"]
        if not isinstance(analyzed, list):
            analyzed = []
    except Exception as e:
        raise ValueError(f"Failed to parse Gemini Batch Analysis JSON: {e}")

    # Fallback merge if count mismatch
    final_opportunities = []
    for idx, c in enumerate(candidates):
        item = analyzed[idx] if idx < len(analyzed) and isinstance(analyzed[idx], dict) else {}
        merged = {
            "company_name": item.get("company_name") or c.get("company_name") or "Unknown Company",
            "website": item.get("website") or c.get("website") or "",
            "location": item.get("location") or c.get("location") or "",
            "industry": item.get("industry") or c.get("industry") or "",
            "company_size": item.get("company_size") or c.get("company_size") or "",
            "description": item.get("description") or c.get("description") or "",
            "icp_fit_score": int(item.get("icp_fit_score", 70)),
            "intent_score": int(item.get("intent_score", 65)),
            "timing_score": int(item.get("timing_score", 60)),
            "overall_score": int(item.get("overall_score", 65)),
            "why_now": item.get("why_now") or "Insufficient evidence of a current trigger.",
            "reason": item.get("reason") or "Evaluated based on search profile.",
            "recommended_action": item.get("recommended_action") or "Research company leadership.",
            "confidence": item.get("confidence") or "medium",
            "signals": item.get("signals") or [e.get("signal") for e in c.get("evidence_snippets", []) if e.get("signal")],
            "evidence": item.get("evidence") or [
                {
                    "signal": e.get("signal", "Signal"),
                    "description": e.get("snippet", "Observed via web search."),
                    "source_url": e.get("source_url", c.get("website", "")),
                    "source_title": e.get("source_title", "Search Result")
                } for e in c.get("evidence_snippets", [])
            ]
        }
        final_opportunities.append(merged)

    return final_opportunities, prompt, raw_text


# ====================================================================
# MASTER PIPELINE (SEPARATED DATA COLLECTION & SINGLE GEMINI CALL)
# ====================================================================
def run_gtm_pipeline(offer: str, target_icp: str, additional_context: str = "") -> List[Dict[str, Any]]:
    """
    Executes the GTM Opportunity Pipeline with complete separation of data collection and Gemini analysis:
    1. Local Python Search Query Generation (No Gemini)
    2. Direct Search API Execution (Bing / Google CSE)
    3. Public Web Evidence Collection & Normalization
    4. Save Complete Collected Telemetry to output/gtm_debug_<timestamp>.json
    5. SINGLE Gemini Batch Opportunity Analysis Request
    6. Save to SQLite database
    """
    run_started_at = datetime.now().isoformat()
    timestamp_filename = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    debug_file_path = os.path.join(output_dir, f"gtm_debug_{timestamp_filename}.json")

    telemetry = {
        "run_started_at": run_started_at,
        "user_input": {
            "offer": offer,
            "target_icp": target_icp,
            "additional_context": additional_context
        },
        "generated_search_queries": [],
        "search_engine_used": None,
        "raw_search_results": [],
        "normalized_candidates": [],
        "evidence": [],
        "gemini_analysis_input": {},
        "gemini_analysis_output": {},
        "final_opportunities": [],
        "run_completed_at": None,
        "debug_log_path": debug_file_path
    }

    # Step 1: Local Search Query Generation
    print("[GTM ENGINE] Step 1: Local Search Strategy Generation (Python)...")
    queries = generate_local_search_queries(offer, target_icp, additional_context)
    telemetry["generated_search_queries"] = queries

    # Step 2 & 3: Direct Search API Data Collection
    print("[GTM ENGINE] Step 2: Executing Direct Search APIs (Bing / Google CSE)...")
    raw_search_results, engine_used = execute_direct_search_apis(queries)
    telemetry["search_engine_used"] = engine_used
    telemetry["raw_search_results"] = raw_search_results

    if not raw_search_results:
        print("[GTM ENGINE] No search results returned from Search API.")
        telemetry["run_completed_at"] = datetime.now().isoformat()
        with open(debug_file_path, "w", encoding="utf-8") as f:
            json.dump(telemetry, f, indent=2, default=str)
        return []

    # Step 4: Public Web Evidence Collection & Normalization
    print("[GTM ENGINE] Step 3: Normalizing Candidates & Collecting Web Evidence...")
    normalized_candidates = normalize_search_results_into_candidates(raw_search_results)
    telemetry["normalized_candidates"] = normalized_candidates
    telemetry["evidence"] = [ev for c in normalized_candidates for ev in c.get("evidence_snippets", [])]

    if not normalized_candidates:
        print("[GTM ENGINE] No candidate companies normalized from search results.")
        telemetry["run_completed_at"] = datetime.now().isoformat()
        with open(debug_file_path, "w", encoding="utf-8") as f:
            json.dump(telemetry, f, indent=2, default=str)
        return []

    # Step 5: Single Gemini Batch Analysis
    print(f"[GTM ENGINE] Step 4: Analyzing {len(normalized_candidates)} candidates via Gemini ({GTM_MODEL})...")
    analyzed_opps, batch_prompt, raw_gemini_output = batch_analyze_opportunities(
        offer, target_icp, additional_context, normalized_candidates
    )

    telemetry["gemini_analysis_input"] = {
        "prompt_sent": batch_prompt
    }
    telemetry["gemini_analysis_output"] = {
        "raw_response": raw_gemini_output,
        "parsed_opportunities": analyzed_opps
    }

    # Step 6: Save Opportunities to SQLite
    print(f"[GTM ENGINE] Step 5: Saving {len(analyzed_opps)} opportunities to SQLite...")
    saved_opportunities = save_opportunities(analyzed_opps)

    telemetry["final_opportunities"] = saved_opportunities
    telemetry["run_completed_at"] = datetime.now().isoformat()

    # Write debug telemetry file to output/gtm_debug_<timestamp>.json
    with open(debug_file_path, "w", encoding="utf-8") as f:
        json.dump(telemetry, f, indent=2, default=str)

    print(f"[GTM ENGINE] GTM Debug telemetry saved to: {debug_file_path}")
    return saved_opportunities
