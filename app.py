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
    get_all_opportunities,
    get_or_create_user,
    get_user_gtm_context,
    save_user_gtm_context,
    rewrite_gtm_context_field
)

from config import Config
from app.security.csrf import init_csrf
from app.security.limiter import init_limiter
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

    status_data = check_linkedin_session()
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

    else:
        session.pop("user_id", None)
        session.pop("linkedin_id", None)

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
    status = check_linkedin_session()
    if status.get("authenticated"):
        return jsonify({"success": True, "already_authenticated": True, "message": "LinkedIn session already active."})

    result = launch_interactive_linkedin_login()
    session.pop("app_logged_out", None)
    return jsonify(result)

@app.route("/api/logout-linkedin-session", methods=["POST"])
def api_logout_linkedin_session():
    result = logout_linkedin_session()
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

@app.route("/api/extract-profile", methods=["POST"])
def api_extract_profile():
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Please provide a valid JSON payload."}), 400

    profile_url = (data.get("profile_url") or "").strip()
    if not profile_url:
        return jsonify({"success": False, "error": "Please enter a valid LinkedIn profile URL."}), 400

    try:
        extraction_data = extract_linkedin_profile(profile_url)
        return jsonify({"success": True, "data": extraction_data})
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Profile extraction failed: {str(e)}. Please verify your LinkedIn session and try again."
        }), 500

@app.route("/api/optimize-profile", methods=["POST"])
def api_optimize_profile():
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Please provide a valid profile object."}), 400

    extracted_profile = data.get("profile") or data
    if not extracted_profile:
        return jsonify({"success": False, "error": "Extracted profile data is missing."}), 400

    gtm_context = data.get("gtm_context")

    try:
        optimization_data = optimize_linkedin_profile(extracted_profile, gtm_context)
        return jsonify({"success": True, "data": optimization_data})
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Profile optimization failed: {str(e)}"
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
    Returns the authenticated user's saved GTM context (offer, ICP, additional_context)
    for read-only display in the GTM frontend.
    """
    user_id = session.get("user_id")
    if not user_id:
        # Attempt to resolve from active LinkedIn session
        try:
            status = check_linkedin_session()
            if status.get("authenticated"):
                user = get_or_create_user(
                    linkedin_id=status.get("linkedin_id", ""),
                    name=status.get("name"),
                    profile_url=status.get("profile_url")
                )
                if user:
                    user_id = user["user_id"]
                    session["user_id"] = user_id
        except Exception:
            pass

    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401

    ctx = get_user_gtm_context(user_id)
    if not ctx or not ctx.get("onboarding_completed"):
        return jsonify({"success": False, "error": "Onboarding not completed. Please complete onboarding first."}), 400

    return jsonify({
        "success": True,
        "data": {
            "offer": ctx.get("offer", ""),
            "target_icp": ctx.get("target_icp", ""),
            "additional_context": ctx.get("additional_context", ""),
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
def api_find_gtm_opportunities():
    """
    Starts the GTM opportunity discovery pipeline.
    The frontend sends an empty body {}.
    The backend resolves the authenticated user and loads offer/ICP/context from the database.
    """
    print("[GTM API DEBUG] POST /api/gtm-opportunities/find RECEIVED", flush=True)
    import traceback
    print("\n[GTM DEBUG] Find Opportunities request received")

    # Resolve authenticated user from session
    user_id = session.get("user_id")
    if not user_id:
        try:
            status = check_linkedin_session()
            if status.get("authenticated"):
                user = get_or_create_user(
                    linkedin_id=status.get("linkedin_id", ""),
                    name=status.get("name"),
                    profile_url=status.get("profile_url")
                )
                if user:
                    user_id = user["user_id"]
                    session["user_id"] = user_id
        except Exception as ex:
            print("[GTM ERROR] Stage: LinkedIn session check")
            print(f"[GTM ERROR] Exception type: {type(ex).__name__}")
            print(f"[GTM ERROR] Message: {str(ex)}")
            traceback.print_exc()

    print(f"[GTM DEBUG] Current user/session: {user_id or 'NOT AUTHENTICATED'}")

    if not user_id:
        print("[GTM ERROR] Stage: Authentication check")
        print("[GTM ERROR] Exception type: AuthError")
        print("[GTM ERROR] Message: Not authenticated. Please connect your LinkedIn session.")
        return jsonify({"success": False, "error": "Not authenticated. Please connect your LinkedIn session."}), 401

    # Load saved GTM context from database
    print("[GTM DEBUG] Loading saved GTM context...")
    try:
        ctx = get_user_gtm_context(user_id)
    except Exception as dberr:
        print("[GTM ERROR] DATABASE FAILURE")
        print(f"[GTM ERROR] Stage: Loading GTM context from DB")
        print(f"[GTM ERROR] Exception type: {type(dberr).__name__}")
        print(f"[GTM ERROR] Message: {str(dberr)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Database error loading context: {str(dberr)}"}), 500

    if not ctx:
        print("[GTM ERROR] Stage: Loading GTM context")
        print("[GTM ERROR] Exception type: ContextMissingError")
        print("[GTM ERROR] Message: Onboarding not completed. Please complete the onboarding questions first.")
        return jsonify({
            "success": False,
            "error": "Onboarding not completed. Please complete the onboarding questions first."
        }), 400

    offer = str(ctx.get("offer") or "").strip()
    target_icp = str(ctx.get("target_icp") or "").strip()
    additional_context = str(ctx.get("additional_context") or "").strip()

    print(f"[GTM DEBUG] Offer found: {'YES' if offer else 'NO'}")
    print(f"[GTM DEBUG] ICP found: {'YES' if target_icp else 'NO'}")
    print(f"[GTM DEBUG] Additional context found: {'YES' if additional_context else 'NO'}")

    if not offer or not target_icp:
        print("[GTM ERROR] Stage: Validating GTM context")
        print("[GTM ERROR] Exception type: ValueError")
        print("[GTM ERROR] Message: Saved onboarding context is incomplete.")
        return jsonify({
            "success": False,
            "error": "Saved onboarding context is incomplete. Please re-complete the onboarding questions."
        }), 400

    try:
        print("[GTM DEBUG] Starting GTM engine...")
        print("[GTM API DEBUG] About to call GTM pipeline", flush=True)
        opportunities = run_gtm_pipeline(offer, target_icp, additional_context)
        print("[GTM API DEBUG] GTM pipeline returned", flush=True)
        print("[GTM DEBUG] Sending response to frontend")
        print("[GTM DEBUG] Request completed successfully")
        return jsonify({
            "success": True,
            "count": len(opportunities),
            "opportunities": opportunities
        })
    except Exception as e:
        print(f"[GTM API DEBUG] ROUTE ERROR: {e}", flush=True)
        err_str = str(e)
        print(f"[GTM ERROR] Stage: GTM pipeline execution")
        print(f"[GTM ERROR] Exception type: {type(e).__name__}")
        print(f"[GTM ERROR] Message: {err_str}")
        traceback.print_exc()

        if "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str:
            print("[GTM ERROR] GEMINI QUOTA/RATE LIMIT")
            return jsonify({
                "success": False,
                "error": "Gemini API quota exceeded. Please try again after the quota resets."
            }), 429

        return jsonify({"success": False, "error": f"GTM discovery failed: {str(e)}"}), 500


@app.route("/api/gtm-opportunities", methods=["GET"])
def api_get_gtm_opportunities():
    try:
        opportunities = get_all_opportunities()
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
