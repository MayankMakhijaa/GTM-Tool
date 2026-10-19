from flask import Flask, request, jsonify, render_template, send_from_directory, Response, stream_with_context, session, send_file
from flask_cors import CORS
import os
import time
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

from parser import parse_pasted_comments
from analyzer import analyze_comments
from excel import generate_excel, generate_excel_in_memory
from legacy.historical import get_historical_email_leads, get_all_historical_leads
import legacy.leads_db as leads_db
from legacy.profile_extractor import (
    extract_linkedin_profile,
    extract_linkedin_profile_generator,
    check_linkedin_session,
    launch_interactive_linkedin_login,
    logout_linkedin_session
)
from profile_optimizer import optimize_linkedin_profile
from legacy.gtm_engine import (
    init_db as init_gtm_db,
    run_gtm_pipeline,
    get_all_opportunities as legacy_get_all_opportunities,
    get_or_create_user,
    get_user_gtm_context as legacy_get_user_gtm_context,
    save_user_gtm_context,
    rewrite_gtm_context_field
)
from app.services.gtm_pipeline_service import (
    get_user_gtm_context,
    start_gtm_research_job,
    get_user_opportunities
)
from app.models.all_models import ResearchJobs

from config import Config
from app.security.csrf import init_csrf
from app.security.limiter import init_limiter, limiter
from app.routes.auth import auth_bp
from app.routes.onboarding import onboarding_bp
from app.routes.pages import pages_bp
from app.database import init_db, db_session

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
init_csrf(app)
init_limiter(app)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(onboarding_bp)
app.register_blueprint(pages_bp)

# Close session at end of request
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

CORS(app)

@app.before_request
def debug_request_logger():
    print(f"[FLASK REQUEST DEBUG] {request.method} {request.path}", flush=True)

OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes

@app.before_request
def check_session_inactivity():
    if session.get("user_id") and not session.get("app_logged_out"):
        now = time.time()
        last_active = session.get("last_activity")
        if last_active and (now - last_active > SESSION_TIMEOUT_SECONDS):
            session.clear()
            session["app_logged_out"] = True
        else:
            session["last_activity"] = now



@app.route("/api/linkedin-session-status", methods=["GET"])
def api_linkedin_session_status():
    if session.get("app_logged_out"):
        return jsonify({
            "success": True,
            "data": {
                "authenticated": False,
                "user": None,
                "gtm_context": None,
                "onboarding_completed": False
            }
        })

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "success": True,
            "data": {
                "authenticated": False,
                "user": None,
                "gtm_context": None,
                "onboarding_completed": False
            }
        })

    status_data = check_linkedin_session(user_id)
    is_auth = status_data.get("authenticated", False)
    linkedin_id = status_data.get("linkedin_id")

    user_info = None
    gtm_ctx = None
    onboarding_completed = False

    if is_auth:
        prof_url = status_data.get("profile_url")
        l_id = linkedin_id or f"session_member_{int(time.time())}"
        user_info = get_or_create_user(
            linkedin_id=l_id,
            name=status_data.get("name"),
            profile_url=prof_url
        )
        if user_info:
            session["user_id"] = user_info["user_id"]
            session["linkedin_id"] = user_info.get("linkedin_id", l_id)

        user_id = session.get("user_id")
        if user_id:
            gtm_ctx = get_user_gtm_context(user_id)
            if gtm_ctx and gtm_ctx.get("onboarding_completed") == 1:
                onboarding_completed = True

    status_data["user"] = user_info
    status_data["gtm_context"] = gtm_ctx
    status_data["onboarding_completed"] = onboarding_completed

    return jsonify({"success": True, "data": status_data})

@app.route("/api/app-logout", methods=["POST"])
def api_app_logout():
    """
    Clears current Flask/application session state and in-memory user context.
    Does NOT destroy persistent Playwright browser profile or database data.
    """
    session.clear()
    session["app_logged_out"] = True
    return jsonify({"success": True, "message": "Application session logged out successfully."})

@app.route("/api/onboarding/save-gtm-context", methods=["POST"])
def api_save_gtm_context():
    data = request.get_json() or {}
    offer = str(data.get("offer") or "").strip()
    target_icp = str(data.get("target_icp") or data.get("icp") or "").strip()
    additional_context = str(data.get("additional_context") or data.get("context") or "").strip()

    if not offer or not target_icp:
        return jsonify({"success": False, "error": "Offer and Target ICP are required."}), 400

    user_id = session.get("user_id")
    if not user_id:
        # Check if active linkedin session can be identified
        session_status = check_linkedin_session()
        l_id = session_status.get("linkedin_id")
        if l_id:
            user = get_or_create_user(l_id, name=session_status.get("name"), profile_url=session_status.get("profile_url"))
            if user:
                user_id = user["user_id"]
                session["user_id"] = user_id

    if not user_id:
        return jsonify({"success": False, "error": "No authenticated user session found."}), 401

    saved_context = save_user_gtm_context(user_id, offer, target_icp, additional_context)
    return jsonify({"success": True, "data": saved_context})

@app.route("/api/open-linkedin-session", methods=["POST"])
def api_open_linkedin_session():
    session.pop("app_logged_out", None)
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "success": False,
            "error": "UNAUTHORIZED",
            "message": "Please log in to your account before connecting LinkedIn."
        }), 401

    status = check_linkedin_session(user_id)
    if status.get("authenticated"):
        return jsonify({"success": True, "already_authenticated": True, "message": "LinkedIn session already active."})

    result = launch_interactive_linkedin_login(user_id)
    session.pop("app_logged_out", None)
    return jsonify(result)

@app.route("/api/logout-linkedin-session", methods=["POST"])
def api_logout_linkedin_session():
    user_id = session.get("user_id")
    result = logout_linkedin_session(user_id)
    session.clear()
    return jsonify(result)

@app.route("/api/extract-profile-stream", methods=["GET"])
def api_extract_profile_stream():
    profile_url = (request.args.get("profile_url") or "").strip()
    if not profile_url:
        return jsonify({"success": False, "error": "Please enter a valid LinkedIn profile URL."}), 400

    raw_selected = request.args.get("selected_sections")
    selected_sections = None
    if raw_selected:
        selected_sections = [s.strip().lower() for s in raw_selected.split(",") if s.strip()]

    def generate():
        try:
            for event in extract_linkedin_profile_generator(profile_url, selected_sections=selected_sections):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")



def persist_extracted_linkedin_profile(user_id: int, extraction_data: dict):
    """
    Normalizes and persists extracted LinkedIn profile data to UsersLinkedinDetails for the given user_id.
    - Preserves existing non-empty values when incoming fields are empty/omitted (non-destructive).
    - Merges rich fields into profile_data JSONB.
    - Guarantees 1 record per user_id without creating duplicate rows.
    """
    from app.models.all_models import UsersLinkedinDetails
    from app.database import db_session
    import re

    if not user_id:
        raise ValueError("user_id is required to persist LinkedIn profile.")

    li_details = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    if not li_details:
        li_details = UsersLinkedinDetails(user_id=user_id)
        db_session.add(li_details)

    if not extraction_data or not isinstance(extraction_data, dict):
        db_session.commit()
        return li_details

    prof = extraction_data.get("profile") if isinstance(extraction_data.get("profile"), dict) else extraction_data

    # Canonical scalar string fields
    string_fields = ["name", "headline", "about", "current_position", "location"]
    for field in string_fields:
        val = prof.get(field)
        if isinstance(val, str) and val.strip():
            setattr(li_details, field, val.strip())

    # Canonical list fields (JSONB)
    list_fields = ["experience", "education", "skills"]
    for field in list_fields:
        val = prof.get(field)
        if isinstance(val, list) and len(val) > 0:
            setattr(li_details, field, val)

    # Profile URL
    extracted_url = extraction_data.get("source_url") or prof.get("profile_url")
    if isinstance(extracted_url, str) and extracted_url.strip() and "linkedin.com" in extracted_url:
        li_details.profile_url = extracted_url.strip()

    # LinkedIn ID
    raw_linkedin_id = prof.get("linkedin_id")
    if not raw_linkedin_id and li_details.profile_url:
        match = re.search(r"linkedin\.com/in/([^/?#]+)", li_details.profile_url)
        if match:
            raw_linkedin_id = match.group(1).strip()
    if raw_linkedin_id and isinstance(raw_linkedin_id, str) and raw_linkedin_id.strip():
        existing_owner = db_session.query(UsersLinkedinDetails).filter(
            UsersLinkedinDetails.linkedin_id == raw_linkedin_id.strip(),
            UsersLinkedinDetails.user_id != user_id
        ).first()
        if not existing_owner:
            li_details.linkedin_id = raw_linkedin_id.strip()

    # Rich fields mapped into profile_data JSONB
    existing_profile_data = dict(li_details.profile_data or {})
    rich_fields = [
        "profile_photo_url", "top_skills", "certifications", "licenses",
        "projects", "featured", "honors_awards", "publications",
        "courses", "volunteer_experience", "languages",
        "organizations", "recommendations", "other_sections"
    ]
    for key in rich_fields:
        val = prof.get(key)
        if val is not None:
            if isinstance(val, (list, dict)) and len(val) > 0:
                existing_profile_data[key] = val
            elif isinstance(val, str) and val.strip():
                existing_profile_data[key] = val.strip()

    li_details.profile_data = existing_profile_data

    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise e

    return li_details


def has_usable_profile_data(li_details) -> bool:
    """
    Validates whether UsersLinkedinDetails contains real, usable profile data for optimization.
    Must have identity (name or headline) and substantive profile content.
    """
    if not li_details:
        return False

    has_name = bool(li_details.name and str(li_details.name).strip())
    has_headline = bool(li_details.headline and str(li_details.headline).strip())
    has_identity = has_name or has_headline

    has_about = bool(li_details.about and str(li_details.about).strip())
    has_experience = bool(isinstance(li_details.experience, list) and len(li_details.experience) > 0)
    has_skills = bool(isinstance(li_details.skills, list) and len(li_details.skills) > 0)
    has_position = bool(li_details.current_position and str(li_details.current_position).strip())
    has_education = bool(isinstance(li_details.education, list) and len(li_details.education) > 0)

    pdata = li_details.profile_data if isinstance(li_details.profile_data, dict) else {}
    has_rich_content = any(
        isinstance(pdata.get(k), list) and len(pdata[k]) > 0
        for k in ["certifications", "projects", "featured", "top_skills"]
    )

    has_substantive = has_about or has_experience or has_skills or has_position or has_education or has_rich_content
    return has_identity and has_substantive


@app.route("/api/extract-profile", methods=["POST"])
def api_extract_profile():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Please provide a valid JSON payload."}), 400

    profile_url = (data.get("profile_url") or data.get("linkedin_url") or "").strip()
    user_id = getattr(request, "user_id", None) or session.get("user_id")
    
    li_details = None
    if user_id:
        from app.models.all_models import UsersLinkedinDetails
        from app.database import db_session
        li_details = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if not profile_url and li_details and li_details.profile_url:
            profile_url = li_details.profile_url

    if not profile_url:
        return jsonify({"success": False, "error": "Please enter a valid LinkedIn profile URL."}), 400

    try:
        from legacy.profile_extractor import extract_linkedin_profile
        extraction_data = extract_linkedin_profile(profile_url, linkedin_details=li_details)
        
        if user_id and extraction_data:
            li_details = persist_extracted_linkedin_profile(user_id, extraction_data)

        returned_profile = extraction_data.get("profile") if isinstance(extraction_data, dict) and "profile" in extraction_data else extraction_data
        return jsonify({"success": True, "profile": returned_profile})
    except Exception as e:
        try:
            from app.database import db_session
            db_session.rollback()
        except Exception:
            pass
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Profile extraction failed: {str(e)}. Please verify your LinkedIn session and try again."
        }), 500


@app.route("/api/optimize-profile", methods=["POST"])
def api_optimize_profile():
    from app.models.all_models import UsersLinkedinDetails, UsersICP
    from app.database import db_session
    import logging

    user_id = getattr(request, "user_id", None) or session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "UNAUTHORIZED", "message": "Authentication required."}), 401

    logging.info(f"[Profile Analysis] User ID: {user_id}")

    linkedin_profile = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()

    # If no LinkedIn record exists
    if not linkedin_profile:
        return jsonify({
            "success": False,
            "error": "NO_LINKEDIN_CONNECTION",
            "message": "LinkedIn profile is not connected. Please connect your LinkedIn account first."
        }), 404

    # Check whether profile has usable data; if not, attempt on-demand extraction
    if not has_usable_profile_data(linkedin_profile):
        logging.info(f"[Profile Analysis] No usable profile data in DB for user {user_id}. Attempting automatic extraction.")

        if not linkedin_profile.auth_data_encrypted:
            return jsonify({
                "success": False,
                "error": "NO_LINKEDIN_CREDENTIALS",
                "message": "LinkedIn credentials not found. Please connect your LinkedIn account before optimizing."
            }), 400

        # Validate stored session before attempting extraction
        from app.integrations.linkedin.voyager_client import validate_user_session
        session_val = validate_user_session(user_id)
        if not session_val.get("valid", False):
            category = session_val.get("category", "unknown")
            if category in ("expired", "revoked"):
                return jsonify({
                    "success": False,
                    "error": "SESSION_EXPIRED",
                    "message": "LinkedIn session has expired or was revoked. Please reconnect your LinkedIn account."
                }), 401
            else:
                return jsonify({
                    "success": False,
                    "error": "SESSION_INVALID",
                    "message": f"LinkedIn session is not active ({session_val.get('message', 'invalid session')}). Please reconnect."
                }), 400

        # Determine target profile URL
        req_data = request.get_json(silent=True) or {}
        profile_url = (req_data.get("profile_url") or req_data.get("linkedin_url") or "").strip()
        if not profile_url and linkedin_profile.profile_url:
            profile_url = linkedin_profile.profile_url
        if not profile_url and linkedin_profile.linkedin_id:
            profile_url = f"https://www.linkedin.com/in/{linkedin_profile.linkedin_id}"

        # If profile_url still unknown, try Voyager /me lookup
        if not profile_url:
            try:
                from app.integrations.linkedin.voyager_client import create_voyager_client_from_db
                voyager = create_voyager_client_from_db(user_id)
                if voyager:
                    user_prof = voyager.get_user_profile()
                    mini = user_prof.get("miniProfile") or {}
                    public_id = mini.get("publicIdentifier")
                    if public_id:
                        profile_url = f"https://www.linkedin.com/in/{public_id}"
            except Exception as voyager_err:
                logging.warning(f"[Profile Analysis] Voyager /me profile resolution failed: {voyager_err}")

        if not profile_url:
            return jsonify({
                "success": False,
                "error": "PROFILE_URL_REQUIRED",
                "message": "LinkedIn profile URL is required to retrieve profile data before optimization."
            }), 400

        # Perform extraction
        try:
            from legacy.profile_extractor import extract_linkedin_profile
            extraction_data = extract_linkedin_profile(profile_url, linkedin_details=linkedin_profile)
            linkedin_profile = persist_extracted_linkedin_profile(user_id, extraction_data)
        except Exception as extract_err:
            try:
                db_session.rollback()
            except Exception:
                pass
            logging.error(f"[Profile Analysis] Extraction failed for user {user_id}: {extract_err}")
            err_msg = str(extract_err)
            if any(k in err_msg.lower() for k in ["session is not authenticated", "authwall", "login"]):
                return jsonify({
                    "success": False,
                    "error": "SESSION_EXPIRED",
                    "message": "LinkedIn session is not authenticated. Please reconnect your LinkedIn account."
                }), 401
            return jsonify({
                "success": False,
                "error": "EXTRACTION_FAILED",
                "message": f"Failed to retrieve LinkedIn profile data: {err_msg}"
            }), 400

        # Re-verify profile is usable after extraction
        if not has_usable_profile_data(linkedin_profile):
            return jsonify({
                "success": False,
                "error": "EXTRACTION_FAILED",
                "message": "Retrieved LinkedIn profile contains insufficient data. Cannot optimize an empty profile."
            }), 400

    # Build normalized profile payload for optimizer
    extracted_profile = {
        "name": linkedin_profile.name,
        "headline": linkedin_profile.headline,
        "location": linkedin_profile.location,
        "current_position": linkedin_profile.current_position,
        "about": linkedin_profile.about,
        "experience": linkedin_profile.experience or [],
        "education": linkedin_profile.education or [],
        "skills": linkedin_profile.skills or []
    }
    if linkedin_profile.profile_data and isinstance(linkedin_profile.profile_data, dict):
        for k, v in linkedin_profile.profile_data.items():
            if k not in extracted_profile or not extracted_profile[k]:
                extracted_profile[k] = v

    icp_profile = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    logging.info(f"[Profile Analysis] Profile loaded: YES")
    logging.info(f"[Profile Analysis] ICP loaded: {'YES' if icp_profile else 'NO'}")

    gtm_context = None
    if icp_profile:
        gtm_context = {
            "target_customer": icp_profile.target_customer,
            "company_size": icp_profile.company_size,
            "revenue_range": icp_profile.revenue_range,
            "target_jobs_roles": icp_profile.target_jobs_roles,
            "industry": icp_profile.industry,
            "location": icp_profile.location,
            "keywords": icp_profile.keywords,
            "exclusions": icp_profile.exclusions
        }

    try:
        import profile_optimizer
        logging.info("[Profile Analysis] Gemini analysis: STARTED")
        optimization_data = profile_optimizer.optimize_linkedin_profile(extracted_profile, gtm_context)

        num_sections = len(optimization_data.get("section_analysis", []))
        score = optimization_data.get("overall_score", 0)
        logging.info(f"[Profile Analysis] Sections analyzed: {num_sections}")
        logging.info(f"[Profile Analysis] Overall score: {score}")
        logging.info("[Profile Analysis] Analysis completed")

        # Cache to DB
        linkedin_profile.optimization_suggestions = optimization_data
        db_session.commit()

        return jsonify({"success": True, "data": optimization_data}), 200
    except Exception as e:
        db_session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "OPTIMIZATION_FAILED",
            "message": f"Profile optimization failed: {str(e)}"
        }), 500

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Please provide pasted LinkedIn comments."}), 400
    
    raw_text = str(data.get("comments_text") or data.get("pasted_text") or data.get("text") or "").strip()
    if not raw_text:
        return jsonify({"success": False, "error": "Please paste LinkedIn comments before generating leads."}), 400
    
    start_time = time.time()
    
    # 1. Parse raw pasted text using local Python parser
    parsed_comments = parse_pasted_comments(raw_text)
    if not parsed_comments:
        return jsonify({"success": False, "error": "No valid comments could be extracted from the pasted text. Please check your copy-paste content."}), 400
        
    # 2. Analyze comments deterministically with Gemini
    try:
        analyzed_comments = analyze_comments(parsed_comments)
    except Exception as e:
        return jsonify({"success": False, "error": f"Gemini analysis failed: {str(e)}"}), 500

    if not isinstance(analyzed_comments, list) or len(analyzed_comments) == 0:
        return jsonify({"success": False, "error": "Lead analysis could not be completed. Please try again."}), 500
        
    # 3. Filter qualified leads
    qualified_leads: List[Dict[str, Any]] = [c for c in analyzed_comments if isinstance(c, dict) and c.get("lead") is True]
        
    # 4. Insert into database
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401
    
    for lead_data in qualified_leads:
        leads_db.insert_lead(user_id, lead_data)
    
    # Calculate average intent score
    scores = [c.get("lead_score", 0) for c in qualified_leads if isinstance(c.get("lead_score"), (int, float))]
    avg_score = sum(scores) / len(scores) if len(scores) > 0 else 0
    
    processing_time = round(time.time() - start_time, 1)
    
    # Sort leads by score descending for the UI
    qualified_leads.sort(key=lambda x: x.get("lead_score", 0), reverse=True)
    
    return jsonify({
        "success": True,
        "comments_analyzed": len(parsed_comments),
        "qualified_leads_count": len(qualified_leads),
        "avg_lead_intent": round(avg_score, 1),
        "processing_time": processing_time,
        "leads": qualified_leads
    })

@app.route("/api/email-leads", methods=["GET"])
def get_email_leads():
    """
    Returns deduplicated email-qualified leads from the DB for the current user.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401
        
    leads = leads_db.get_email_leads_db(user_id)
    return jsonify({
        "success": True,
        "count": len(leads),
        "leads": leads
    })

@app.route("/api/history-leads", methods=["GET"])
def get_history_leads():
    """
    Returns historical qualified leads for the current user.
    Supports optional from_date and to_date filters.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401
        
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    
    leads = leads_db.get_history_leads_db(user_id, from_date, to_date)
    return jsonify({
        "success": True,
        "count": len(leads),
        "leads": leads
    })

@app.route("/api/download-excel", methods=["GET"])
def download_excel():
    """
    Generates and returns an Excel export for the user's leads, filtered by date.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401
        
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    
    leads = leads_db.get_history_leads_db(user_id, from_date, to_date)
    
    output = generate_excel_in_memory(leads)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return send_file(
        output,
        as_attachment=True,
        download_name=f"linkedin_leads_{timestamp}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/api/gtm-context", methods=["GET"])
def api_get_gtm_context():
    """
    Returns the authenticated user's saved GTM context (offer, ICP, company)
    from PostgreSQL and verifies LinkedIn session validity.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401

    ctx = get_user_gtm_context(user_id)
    if not ctx or not ctx.get("onboarding_completed"):
        return jsonify({
            "success": False,
            "error": "Onboarding not completed. Please complete onboarding first.",
            "data": ctx
        }), 400

    return jsonify({
        "success": True,
        "data": {
            "offer": ctx.get("offer", ""),
            "target_icp": ctx.get("target_icp", ""),
            "company_name": ctx.get("company_name", ""),
            "website_url": ctx.get("website_url", ""),
            "session_valid": ctx.get("session_valid", False),
            "session_category": ctx.get("session_category", "disconnected"),
            "session_message": ctx.get("session_message", ""),
            "active_job": ctx.get("active_job")
        }
    })


@app.route("/api/gtm-context/write-with-ai", methods=["POST"])
def api_write_with_ai():
    data = request.get_json() or {}
    field = data.get("field")
    current_value = data.get("current_value")
    instruction = data.get("instruction")
    
    if not field or not instruction:
        return jsonify({"success": False, "error": "Field and instruction are required."}), 400
        
    try:
        enriched_text = rewrite_gtm_context_field(field, current_value or "", instruction)
        return jsonify({"success": True, "generated_text": enriched_text})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/gtm-opportunities/find", methods=["POST"])
@app.route("/api/gtm/jobs/start", methods=["POST"])
def api_find_gtm_opportunities():
    """
    Starts an asynchronous GTM research run using the dual-discovery pipeline.
    The backend resolves the authenticated user and loads offer/ICP/context from PostgreSQL.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated. Please connect your LinkedIn session."}), 401

    data = request.get_json(silent=True) or {}
    target_leads = int(data.get("target_leads", 25) or 25)
    persona_filter = data.get("persona_filter")

    try:
        result = start_gtm_research_job(
            app=app,
            user_id=user_id,
            target_leads=target_leads,
            persona_filter=persona_filter
        )
        return jsonify({
            "success": True,
            "job_id": result["job_id"],
            "status": result["status"],
            "is_existing": result.get("is_existing", False),
            "message": result.get("message", "")
        })
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to start research job: {str(e)}"}), 500


@app.route("/api/gtm/jobs/<int:job_id>/status", methods=["GET"])
@limiter.limit("1200 per hour; 30 per minute")
def api_get_gtm_job_status(job_id):
    """
    Returns the execution status, progress percentage, and results count for a research job.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401

    job = db_session.query(ResearchJobs).filter_by(id=job_id, user_id=user_id).first()
    if not job:
        return jsonify({"success": False, "error": "Job not found."}), 404

    return jsonify({
        "success": True,
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress or {},
        "results_count": job.results_count or 0,
        "error": job.error_message
    })


@app.route("/api/gtm-opportunities", methods=["GET"])
def api_get_gtm_opportunities():
    """
    Returns all qualified opportunities saved for the user in PostgreSQL.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401

    try:
        opportunities = get_user_opportunities(user_id)
        return jsonify({
            "success": True,
            "count": len(opportunities),
            "opportunities": opportunities
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to fetch opportunities: {str(e)}"}), 500

@app.route("/download/<path:filename>", methods=["GET"])
def download_file(filename):
    # Prevent arbitrary file access
    safe_path = os.path.normpath(filename)
    if safe_path.startswith("..") or "/" in safe_path or "\\" in safe_path:
        return jsonify({"error": "Invalid filename"}), 400
        
    return send_from_directory(OUTPUT_DIR, safe_path, as_attachment=True)

if __name__ == "__main__":
    print("[FLASK DEBUG] Running current app.py instance", flush=True)
    print("[FLASK DEBUG] Registered routes:", flush=True)
    for rule in app.url_map.iter_rules():
        print(f"[FLASK DEBUG] {rule} -> {rule.methods}", flush=True)
    app.run(debug=True, port=5000)
