import os
import json
import time
import sqlite3
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from google import genai
from google.genai import types

DB_PATH = os.path.join(os.getcwd(), "gtm_opportunities.db")

# Model selection: prefer flash, fall back to lite.
# These IDs are confirmed available on this API key via models.list().
GTM_MODEL_PRIMARY = "models/gemini-2.5-pro"
GTM_MODEL_FALLBACK = "models/gemini-3.5-flash-lite"


# ====================================================================
# DATABASE INIT
# ====================================================================
def init_db():
    """Initializes SQLite tables: opportunities, users, user_gtm_context."""
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            linkedin_id TEXT UNIQUE NOT NULL,
            name TEXT,
            profile_url TEXT,
            created_at TEXT NOT NULL,
            last_login TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_gtm_context (
            user_id INTEGER PRIMARY KEY,
            offer TEXT NOT NULL,
            target_icp TEXT NOT NULL,
            additional_context TEXT,
            onboarding_completed INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
    """)
    conn.commit()
    conn.close()


# ====================================================================
# URL NORMALIZATION
# ====================================================================
def normalize_linkedin_profile_url(url: Optional[str]) -> Optional[str]:
    """Normalizes a LinkedIn profile URL for reliable identity matching."""
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    parsed = urllib.parse.urlparse(cleaned)
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "www.linkedin.com").lower()
    path = parsed.path.rstrip("/").lower()
    return f"{scheme}://{netloc}{path}"


# ====================================================================
# USER MANAGEMENT
# ====================================================================
def get_or_create_user(
    linkedin_id: str,
    name: Optional[str] = None,
    profile_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Finds or creates a user by normalized profile_url (primary) or linkedin_id."""
    if not linkedin_id and not profile_url:
        return None

    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    norm_url = normalize_linkedin_profile_url(profile_url)
    user_row = None

    if norm_url:
        cursor.execute(
            "SELECT * FROM users WHERE profile_url IS NOT NULL AND profile_url != '' ORDER BY user_id ASC"
        )
        for u in cursor.fetchall():
            if normalize_linkedin_profile_url(u["profile_url"]) == norm_url:
                user_row = u
                break

    if not user_row and linkedin_id:
        cursor.execute("SELECT * FROM users WHERE linkedin_id = ? ORDER BY user_id ASC", (linkedin_id,))
        user_row = cursor.fetchone()

    if user_row:
        user_id = user_row["user_id"]
        cursor.execute(
            "UPDATE users SET name = ?, profile_url = ?, last_login = ? WHERE user_id = ?",
            (name or user_row["name"], profile_url or user_row["profile_url"], now_iso, user_id)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = dict(cursor.fetchone())
        conn.close()
        return result
    else:
        cursor.execute(
            "INSERT INTO users (linkedin_id, name, profile_url, created_at, last_login) VALUES (?, ?, ?, ?, ?)",
            (linkedin_id or f"member_{int(time.time())}", name or "LinkedIn Member", profile_url or "", now_iso, now_iso)
        )
        conn.commit()
        user_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = dict(cursor.fetchone())
        conn.close()
        return result


# ====================================================================
# GTM CONTEXT (ONBOARDING DATA)
# ====================================================================
def get_user_gtm_context(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves saved onboarding GTM context (offer, ICP, additional_context) for a user."""
    print("[GTM DEBUG] Loading saved GTM context from DB")
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_gtm_context WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        res = dict(row) if row else None
        if res:
            print("[GTM DEBUG] Context loaded successfully")
        else:
            print("[GTM DEBUG] No saved context found for user")
        return res
    except Exception as e:
        print("[GTM ERROR] DATABASE FAILURE")
        print(f"[GTM ERROR] Failed loading GTM context: {e}")
        raise


def save_user_gtm_context(
    user_id: int,
    offer: str,
    target_icp: str,
    additional_context: str = ""
) -> Dict[str, Any]:
    """Saves or updates a user's GTM onboarding context."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    cursor.execute("SELECT user_id FROM user_gtm_context WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()

    if exists:
        cursor.execute("""
            UPDATE user_gtm_context
            SET offer = ?, target_icp = ?, additional_context = ?,
                onboarding_completed = 1, updated_at = ?
            WHERE user_id = ?
        """, (offer, target_icp, additional_context, now_iso, user_id))
    else:
        cursor.execute("""
            INSERT INTO user_gtm_context
                (user_id, offer, target_icp, additional_context, onboarding_completed, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        """, (user_id, offer, target_icp, additional_context, now_iso, now_iso))

    conn.commit()
    conn.close()
    return get_user_gtm_context(user_id) or {}


# ====================================================================
# OPPORTUNITY PERSISTENCE
# ====================================================================
def save_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inserts analyzed opportunities into the SQLite opportunities table."""
    print(f"[GTM DEBUG] Saving {len(opportunities)} opportunities to SQLite")
    try:
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
            recommended_action = str(opp.get("recommended_action") or "Research company and initiate outreach.").strip()
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
            opp_copy = dict(opp)
            opp_copy["id"] = cursor.lastrowid
            opp_copy["created_at"] = now_iso
            saved.append(opp_copy)

        conn.commit()
        conn.close()
        print("[GTM DEBUG] SQLite save completed")
        return saved
    except Exception as e:
        print("[GTM ERROR] DATABASE FAILURE")
        print(f"[GTM ERROR] Failed to save opportunities: {e}")
        raise


def get_all_opportunities() -> List[Dict[str, Any]]:
    """Retrieves all stored opportunities ordered by overall_score descending."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM opportunities ORDER BY overall_score DESC, id DESC")
    results = []
    for r in cursor.fetchall():
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


def clear_opportunities() -> int:
    """Deletes all stored opportunities (used before a fresh run). Returns deleted count."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM opportunities")
    count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM opportunities")
    conn.commit()
    conn.close()
    return count


# ====================================================================
# GEMINI CLIENT + HELPERS
# ====================================================================
def _get_gemini_client() -> genai.Client:
    """Returns an authenticated genai.Client using GEMINI_API_KEY."""
    print("[GTM DEBUG] Gemini initialization...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[GTM ERROR] Stage: Gemini initialization")
        print("[GTM ERROR] Exception type: ValueError")
        print("[GTM ERROR] Message: GEMINI_API_KEY is not set in environment.")
        raise ValueError("GEMINI_API_KEY is not set in environment.")
    return genai.Client(api_key=api_key)


def _clean_json_markdown(raw_text: str) -> str:
    """Strips ```json ... ``` markdown fences if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_json_list(text: str) -> List[Dict[str, Any]]:
    """Parses a JSON array from text, with fallback to bracket extraction."""
    clean = _clean_json_markdown(text)
    try:
        result = json.loads(clean)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("opportunities", "companies", "candidates", "results"):
                if isinstance(result.get(key), list):
                    return result[key]
    except Exception:
        pass

    # Fallback: extract first [...] block
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _call_gemini(
    client: genai.Client,
    model_id: str,
    contents: str,
    config: types.GenerateContentConfig
) -> Tuple[str, str]:
    """
    Calls client.models.generate_content with automatic model fallback.
    Returns (response_text, model_used).
    Raises immediately on 429 quota errors.
    """
    models_to_try = [model_id, GTM_MODEL_FALLBACK]
    if model_id == GTM_MODEL_FALLBACK:
        models_to_try = [GTM_MODEL_FALLBACK]

    last_error = None
    for m in models_to_try:
        print("[GTM DEBUG] Gemini call starting")
        print(f"[GTM DEBUG] Model: {m}")
        print("[GTM DEBUG] API method: client.models.generate_content")
        try:
            res = client.models.generate_content(
                model=m,
                contents=contents,
                config=config
            )
            print("[GTM DEBUG] Gemini call completed")
            return (res.text or ""), m
        except Exception as e:
            err_str = str(e)
            print("[GTM ERROR] Gemini call failed")
            print(f"[GTM ERROR] Model: {m}")
            print(f"[GTM ERROR] Error: {err_str}")
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                print("[GTM ERROR] GEMINI QUOTA/RATE LIMIT")
                raise RuntimeError(
                    f"Gemini API quota exceeded on model {m}. "
                    "Please try again after the quota resets."
                ) from e
            if "404" in err_str or "NOT_FOUND" in err_str or "deprecated" in err_str.lower():
                print(f"[GTM ENGINE] Model {m} not available, trying fallback...")
                last_error = e
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("All Gemini model candidates failed.")


def _call_gemini_with_grounding(
    client: genai.Client,
    model_id: str,
    contents: str
) -> Tuple[str, List[Dict[str, Any]], List[str], str]:
    """
    Calls Gemini with Google Search Grounding.
    Returns (response_text, grounding_sources, search_queries, model_used).
    grounding_sources: list of {title, uri} dicts from grounding chunks.
    """
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
    )
    text, model_used = _call_gemini(client, model_id, contents, config)

    # The AFC warning is benign — grounding still works
    sources: List[Dict[str, Any]] = []
    queries: List[str] = []
    return text, sources, queries, model_used


# ====================================================================
# STEP 1: GROUNDED DISCOVERY
# ====================================================================
def _discover_companies_with_grounding(
    offer: str,
    target_icp: str,
    additional_context: str,
    client: genai.Client
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Gemini Call #1: Discovers 6-10 real companies using Google Search Grounding.
    Returns (candidates_list, model_used).
    """
    context_block = f"\nADDITIONAL CONTEXT:\n{additional_context}" if additional_context else ""

    prompt = f"""You are an expert B2B market researcher with access to live Google Search.

USER'S OFFER:
{offer}

TARGET ICP (Ideal Customer Profile):
{target_icp}
{context_block}

TASK:
Use Google Search to discover 6 to 10 REAL, publicly-known companies that match this ICP.

Search for companies showing one or more of these signals (based on relevance to the offer and ICP):
- Recent hiring activity relevant to the offer
- Funding rounds (Seed, Series A, B, C, etc.)
- Product launches or major feature releases
- Geographic expansion or new office openings
- Technology adoption relevant to the offer
- Partnerships or integrations announcements
- Leadership changes (new CTO, CPO, VP of Sales, etc.)
- Operational scaling indicators
- Public pain points matching the offer's solution
- Any other timely business signals relevant to the ICP

For each company, extract only verifiable public information:
- Exact company name
- Official website (https://...)
- Location (City, Country) or "Unknown"
- Industry or "Unknown"
- Company size (employee range) or "Unknown"
- Brief description of what they do
- Specific signals found (list them)
- Evidence items: for each signal, include the snippet, the page title, and the source URL

CRITICAL RULES:
- Only include REAL companies. Do not fabricate.
- Do not fabricate signals, evidence, or URLs.
- If a detail cannot be found in public search, use "Unknown" — do not guess.
- Evidence snippets must reflect actual discovered content, not assumptions.

Return ONLY a valid JSON array. No extra text before or after the JSON.

Schema:
[
  {{
    "company_name": "Exact Company Name",
    "website": "https://example.com",
    "location": "City, Country or Unknown",
    "industry": "Industry description or Unknown",
    "company_size": "e.g. 50-200 employees or Unknown",
    "description": "What the company does (1-2 sentences)",
    "signals": ["Signal 1", "Signal 2"],
    "evidence_snippets": [
      {{
        "signal": "Signal label",
        "snippet": "Exact text snippet from the source",
        "source_title": "Page or article title",
        "source_url": "https://source.com/article"
      }}
    ]
  }}
]
"""

    print("[GTM DEBUG] Starting Google Search Grounding...")
    try:
        text, model_used = _call_gemini(
            client,
            GTM_MODEL_PRIMARY,
            prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            )
        )
        print("[GTM DEBUG] Search grounding completed")
    except Exception as e:
        print("[GTM ERROR] GOOGLE SEARCH GROUNDING FAILED")
        print(f"[GTM ERROR] {str(e)}")
        raise

    candidates = _parse_json_list(text)
    if not candidates:
        print(f"[GTM ENGINE] Discovery: no JSON parsed from response. Raw (first 400): {text[:400]}")

    # Validate minimal structure
    valid = []
    for c in candidates:
        if isinstance(c, dict) and c.get("company_name"):
            # Ensure required keys exist with defaults
            c.setdefault("website", "")
            c.setdefault("location", "Unknown")
            c.setdefault("industry", "Unknown")
            c.setdefault("company_size", "Unknown")
            c.setdefault("description", "")
            c.setdefault("signals", [])
            c.setdefault("evidence_snippets", [])
            valid.append(c)

    print(f"[GTM DEBUG] Search results/candidates: {len(valid)}")
    print(f"[GTM DEBUG] Candidates discovered: {len(valid)}")
    return valid, model_used


# ====================================================================
# STEP 2: BATCH OPPORTUNITY ANALYSIS
# ====================================================================
def _batch_analyze_opportunities(
    offer: str,
    target_icp: str,
    additional_context: str,
    candidates: List[Dict[str, Any]],
    client: genai.Client
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Gemini Call #2: Scores and evaluates all candidate companies in a single batch call.
    Returns (analyzed_opportunities, model_used).
    """
    if not candidates:
        return [], GTM_MODEL_PRIMARY

    print("[GTM DEBUG] Starting opportunity analysis...")

    # Build compact candidate list for the prompt (limit evidence snippet size)
    compact = []
    for c in candidates:
        ev = []
        for e in (c.get("evidence_snippets") or [])[:4]:
            if isinstance(e, dict):
                ev.append({
                    "signal": str(e.get("signal") or "Signal")[:80],
                    "snippet": str(e.get("snippet") or "")[:300],
                    "source_title": str(e.get("source_title") or "")[:100],
                    "source_url": str(e.get("source_url") or "")[:200],
                })
        compact.append({
            "company_name": c.get("company_name") or "Unknown",
            "website": c.get("website") or "",
            "location": c.get("location") or "Unknown",
            "industry": c.get("industry") or "Unknown",
            "company_size": c.get("company_size") or "Unknown",
            "description": str(c.get("description") or "")[:300],
            "signals": (c.get("signals") or [])[:5],
            "evidence": ev,
        })

    context_block = f"\nADDITIONAL CONTEXT:\n{additional_context}" if additional_context else ""
    candidates_json = json.dumps(compact, indent=2)

    prompt = f"""You are an expert B2B Go-To-Market Analyst.

Evaluate the following candidate companies against the user's Offer and ICP.

USER'S OFFER:
{offer}

TARGET ICP:
{target_icp}
{context_block}

CANDIDATE COMPANIES WITH COLLECTED EVIDENCE:
{candidates_json}

EVALUATION RULES:
1. Base ALL scores and explanations strictly on the collected evidence above.
2. DO NOT invent signals, events, or facts not present in the evidence.
3. If evidence for a timing trigger is weak or absent, set confidence to "low" and why_now to "Insufficient evidence of a current trigger."
4. Score each company on:
   - icp_fit_score (0-100): How well does this company match the target ICP?
   - intent_score (0-100): How much buying signal or intent is shown in the evidence?
   - timing_score (0-100): How timely is this opportunity based on recent signals?
   - overall_score (0-100): Weighted combination: ICP fit (40%) + intent (35%) + timing (25%)
5. why_now: Explain specifically WHY this is a good moment to approach, tied to actual evidence.
6. recommended_action: Concrete, strategic next step (e.g., "Connect with the new VP of Sales regarding [specific offer angle]").
7. reason: Brief overall evaluation summary.
8. confidence: "high" if strong evidence, "medium" if moderate, "low" if weak.
9. For each company, convert the raw evidence_snippets into clean evidence items.

Return ONLY a valid JSON array. No extra text before or after.

Schema for each opportunity:
[
  {{
    "company_name": "Matches input company_name exactly",
    "website": "https://...",
    "location": "City, Country or Unknown",
    "industry": "Industry",
    "company_size": "Size range",
    "description": "Company description",
    "icp_fit_score": 85,
    "intent_score": 70,
    "timing_score": 75,
    "overall_score": 78,
    "why_now": "Specific reason grounded in evidence.",
    "reason": "Overall evaluation summary.",
    "recommended_action": "Concrete next step.",
    "confidence": "high|medium|low",
    "signals": ["Signal 1", "Signal 2"],
    "evidence": [
      {{
        "signal": "Signal label",
        "description": "Short supporting detail from collected evidence",
        "source_url": "https://...",
        "source_title": "Page title"
      }}
    ]
  }}
]
"""

    config = types.GenerateContentConfig(temperature=0.2)
    text, model_used = _call_gemini(client, GTM_MODEL_PRIMARY, prompt, config)

    analyzed = _parse_json_list(text)
    if not analyzed:
        print(f"[GTM ENGINE] Analysis: no JSON parsed. Raw (first 400): {text[:400]}")

    # Merge: if Gemini returns fewer items than candidates, fill from candidate data
    final = []
    for idx, c in enumerate(compact):
        item = analyzed[idx] if idx < len(analyzed) and isinstance(analyzed[idx], dict) else {}

        # Build evidence: prefer Gemini output, fall back to raw evidence_snippets
        gemini_evidence = item.get("evidence") or []
        if not gemini_evidence:
            gemini_evidence = [
                {
                    "signal": e.get("signal", "Web Signal"),
                    "description": e.get("snippet", "")[:250],
                    "source_url": e.get("source_url", ""),
                    "source_title": e.get("source_title", ""),
                }
                for e in c.get("evidence", [])
            ]

        merged = {
            "company_name": item.get("company_name") or c["company_name"],
            "website": item.get("website") or c["website"],
            "location": item.get("location") or c["location"],
            "industry": item.get("industry") or c["industry"],
            "company_size": item.get("company_size") or c["company_size"],
            "description": item.get("description") or c["description"],
            "icp_fit_score": int(item.get("icp_fit_score", 60)),
            "intent_score": int(item.get("intent_score", 55)),
            "timing_score": int(item.get("timing_score", 50)),
            "overall_score": int(item.get("overall_score", 56)),
            "why_now": item.get("why_now") or "Insufficient evidence of a current trigger.",
            "reason": item.get("reason") or "Evaluated based on available public evidence.",
            "recommended_action": item.get("recommended_action") or "Research company and initiate outreach.",
            "confidence": item.get("confidence") or "low",
            "signals": item.get("signals") or c.get("signals") or [],
            "evidence": gemini_evidence,
        }
        final.append(merged)

    print("[GTM DEBUG] Analysis completed")
    print(f"[GTM DEBUG] Opportunities generated: {len(final)}")
    return final, model_used


# ====================================================================
# MASTER GTM PIPELINE
# ====================================================================
def run_gtm_pipeline(
    offer: str,
    target_icp: str,
    additional_context: str = ""
) -> List[Dict[str, Any]]:
    """
    Executes the full GTM Opportunity Pipeline:
      Call 1: Gemini + Google Search Grounding → discovers real companies + public evidence
      Call 2: Gemini (no tools) → batch evaluates/scores companies
      Saves results to SQLite, writes debug telemetry to output/
      Returns saved opportunities.

    Raises RuntimeError with a user-facing message on Gemini quota exhaustion.
    Raises ValueError if onboarding context is missing.
    """
    if not offer or not target_icp:
        raise ValueError("GTM pipeline requires both 'offer' and 'target_icp'.")

    run_started_at = datetime.now().isoformat()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    debug_path = os.path.join(output_dir, f"gtm_debug_{ts}.json")

    telemetry: Dict[str, Any] = {
        "run_started_at": run_started_at,
        "offer": offer,
        "target_icp": target_icp,
        "additional_context": additional_context,
        "discovery_model": None,
        "analysis_model": None,
        "candidates_count": 0,
        "opportunities_count": 0,
        "run_completed_at": None,
        "debug_path": debug_path,
    }

    client = _get_gemini_client()
    print(f"[GTM DEBUG] Gemini model: {GTM_MODEL_PRIMARY}")

    # Step 1: Grounded discovery
    print("[GTM ENGINE] Step 1: Discovering companies via Gemini + Google Search Grounding...")
    candidates, discovery_model = _discover_companies_with_grounding(
        offer, target_icp, additional_context, client
    )
    telemetry["discovery_model"] = discovery_model
    telemetry["candidates_count"] = len(candidates)

    if not candidates:
        print("[GTM ENGINE] No companies discovered. Aborting pipeline.")
        telemetry["run_completed_at"] = datetime.now().isoformat()
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(telemetry, f, indent=2, default=str)
        return []

    # Step 2: Batch opportunity analysis
    print(f"[GTM ENGINE] Step 2: Analyzing {len(candidates)} candidates via Gemini (no search tools)...")
    analyzed, analysis_model = _batch_analyze_opportunities(
        offer, target_icp, additional_context, candidates, client
    )
    telemetry["analysis_model"] = analysis_model

    if not analyzed:
        print("[GTM ENGINE] Analysis returned no opportunities. Saving candidates as-is with default scores.")
        # Save raw candidates with minimal scoring rather than returning nothing
        analyzed = [
            {
                "company_name": c.get("company_name", "Unknown"),
                "website": c.get("website", ""),
                "location": c.get("location", "Unknown"),
                "industry": c.get("industry", "Unknown"),
                "company_size": c.get("company_size", "Unknown"),
                "description": c.get("description", ""),
                "signals": c.get("signals", []),
                "evidence": [
                    {
                        "signal": e.get("signal", "Signal"),
                        "description": e.get("snippet", "")[:250],
                        "source_url": e.get("source_url", ""),
                        "source_title": e.get("source_title", ""),
                    }
                    for e in (c.get("evidence_snippets") or [])
                ],
                "icp_fit_score": 50,
                "intent_score": 40,
                "timing_score": 40,
                "overall_score": 45,
                "why_now": "Insufficient evidence of a current trigger.",
                "reason": "Discovered via public web search; manual review recommended.",
                "recommended_action": "Research company and evaluate fit manually.",
                "confidence": "low",
            }
            for c in candidates
        ]

    # Step 3: Persist
    print(f"[GTM DEBUG] Saving opportunities...")
    saved = save_opportunities(analyzed)
    print(f"[GTM DEBUG] Opportunities saved")
    telemetry["opportunities_count"] = len(saved)
    telemetry["run_completed_at"] = datetime.now().isoformat()

    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(telemetry, f, indent=2, default=str)
    print(f"[GTM ENGINE] Debug telemetry: {debug_path}")

    return saved
