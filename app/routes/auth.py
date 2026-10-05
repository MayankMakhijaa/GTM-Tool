from flask import Blueprint, request, jsonify
from app.services.auth_service import signup_user, authenticate_user
from app.security.session import set_user_session, clear_user_session, login_required
from app.repositories.user_repository import get_user_by_id
from app.security.limiter import limiter
from app.integrations.linkedin.voyager_client import validate_linkedin_connection, extract_cookies_from_browser, encrypt_credential, create_voyager_client_from_browser
from app.database import db_session
from app.models.all_models import UsersLinkedinDetails, ConnectionStatus
import os
import json
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/signup', methods=['POST'])
@limiter.limit("5 per minute")
def signup():
    data = request.get_json() or {}
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    
    # Check linkedin connection validity before proceeding
    profile_dir = os.path.join(os.getcwd(), "browser_profile")
    if not validate_linkedin_connection(profile_dir):
        return jsonify({
            "success": False,
            "error": "LINKEDIN_NOT_CONNECTED",
            "message": "LinkedIn must be connected to create an account."
        }), 400
        
    try:
        user = signup_user(name, email, phone, password)
        # Auth the user right after signup
        set_user_session(user.user_id)
        
        # Link linkedin account
        jar = extract_cookies_from_browser(profile_dir)
        if jar:
            cookies_dict = {}
            for cookie in jar:
                cookies_dict[cookie.name] = cookie.value
                
            encrypted_data = encrypt_credential(json.dumps(cookies_dict))
            
            li_details = UsersLinkedinDetails(
                user_id=user.user_id,
                auth_data_encrypted=encrypted_data,
                connection_status=ConnectionStatus.CONNECTED.value,
                consent_at=datetime.utcnow()
            )
            
            # Attempt Voyager profile enrichment (Basic Identity Only)
            try:
                voyager = create_voyager_client_from_browser(profile_dir)
                if voyager:
                    me_res = voyager._fetch("/me")
                    if me_res.status_code == 200:
                        me_data = me_res.json()
                        mini = me_data.get("miniProfile", {})
                        
                        public_id = mini.get("publicIdentifier")
                        dash_urn = mini.get("dashEntityUrn", "")
                        
                        li_details.linkedin_id = mini.get("objectUrn") or dash_urn
                        if public_id:
                            li_details.profile_url = f"https://www.linkedin.com/in/{public_id}/"
                        
                        first_name = mini.get("firstName") or ""
                        last_name = mini.get("lastName") or ""
                        li_details.name = f"{first_name} {last_name}".strip()
                        
                        li_details.headline = mini.get("occupation")
                        li_details.profile_source = "VOYAGER_ME"
                        print(f"[Signup] Voyager basic identity fetched successfully for user {user.user_id}")
                    else:
                        print(f"[Signup] Voyager /me returned non-200 status: {me_res.status_code}")
                else:
                    print("[Signup] Failed to instantiate Voyager client.")
            except Exception as e:
                import traceback
                print(f"[Signup] Voyager basic identity extraction failed: {e}")
                traceback.print_exc()
            
            db_session.add(li_details)
            db_session.commit()
            
            # --- START BACKGROUND EXTRACTION ---
            if getattr(li_details, 'profile_url', None):
                import threading
                def background_extract(user_id):
                    try:
                        from app.database import db_session as thread_db
                        from app.models.all_models import UsersLinkedinDetails
                        from legacy.profile_extractor import extract_linkedin_profile
                        import logging
                        
                        li = thread_db.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
                        if not li or not li.profile_url: return
                        
                        logging.info(f"[BACKGROUND] Starting full profile extraction for user {user_id}")
                        ext = extract_linkedin_profile(li.profile_url, linkedin_details=li)
                        
                        if ext and "profile" in ext:
                            prof = ext["profile"]
                            if prof.get("name"): li.name = prof["name"]
                            if prof.get("headline"): li.headline = prof["headline"]
                            if prof.get("about"): li.about = prof["about"]
                            if prof.get("current_position"): li.current_position = prof["current_position"]
                            if prof.get("location"): li.location = prof["location"]
                            if prof.get("experience"): li.experience = prof["experience"]
                            if prof.get("education"): li.education = prof["education"]
                            if prof.get("skills"): li.skills = prof["skills"]
                            
                            existing_data = li.profile_data or {}
                            for key in ["profile_photo_url", "top_skills", "certifications", "licenses", "projects", "featured", "honors_awards", "publications", "courses", "volunteer_experience", "languages", "organizations", "recommendations", "other_sections"]:
                                if prof.get(key): existing_data[key] = prof[key]
                            li.profile_data = existing_data
                            
                            thread_db.commit()
                            logging.info(f"[BACKGROUND] Successfully saved full profile for user {user_id}")
                    except Exception as e:
                        import traceback
                        logging.error(f"[BACKGROUND] Extraction failed for user {user_id}: {e}")
                        traceback.print_exc()

                threading.Thread(target=background_extract, args=(user.user_id,), daemon=True).start()
            # -----------------------------------
            
        return jsonify({
            "success": True,
            "message": "User created successfully",
            "user": {
                "user_id": user.user_id,
                "name": user.name,
                "email_id": user.email_id,
                "phone_no": user.phone_no,
                "onboarding_step": user.onboarding_step,
                "optimization_status": user.optimization_status,
                "is_active": user.is_active
            }
        }), 201
    except ValueError as e:
        error_msg = str(e)
        field = "general"
        if "email" in error_msg.lower(): field = "email"
        elif "phone" in error_msg.lower(): field = "phone"
        elif "password" in error_msg.lower(): field = "password"
        elif "name" in error_msg.lower(): field = "name"
        
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": error_msg,
            "fields": {
                field: error_msg
            }
        }), 400

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json() or {}
    identifier = data.get('identifier')
    password = data.get('password')
    
    user = authenticate_user(identifier, password)
    if not user:
        return jsonify({
            "success": False,
            "error": "INVALID_CREDENTIALS",
            "message": "Invalid credentials"
        }), 401
        
    set_user_session(user.user_id)
    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email_id": user.email_id,
            "phone_no": user.phone_no,
            "onboarding_step": user.onboarding_step,
            "optimization_status": user.optimization_status,
            "is_active": user.is_active
        }
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    clear_user_session()
    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    }), 200

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    from flask import session
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            "authenticated": False
        }), 200
        
    user = get_user_by_id(user_id)
    
    if not user or not user.is_active:
        return jsonify({
            "authenticated": False
        }), 200
        
    return jsonify({
        "authenticated": True,
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email_id": user.email_id,
            "phone_no": user.phone_no,
            "onboarding_step": user.onboarding_step,
            "optimization_status": user.optimization_status,
            "is_active": user.is_active
        }
    }), 200

@auth_bp.route('/linkedin/status', methods=['GET'])
def get_linkedin_status():
    """
    Validates if the current persistent browser has a valid Voyager-authenticated LinkedIn session.
    Does not create a user. Safe for the signup flow.
    """
    profile_dir = os.path.join(os.getcwd(), "browser_profile")
    is_valid = validate_linkedin_connection(profile_dir)
    return jsonify({
        "success": True,
        "connected": is_valid,
        "status": "authenticated" if is_valid else "disconnected"
    })

@auth_bp.route('/linkedin/reconnect', methods=['POST'])
@login_required
def reconnect_linkedin():
    """
    Reconnects the existing user's LinkedIn session from the browser_profile.
    Used when the session is invalid/expired but the user is already onboarded.
    """
    user_id = request.user_id
    
    profile_dir = os.path.join(os.getcwd(), "browser_profile")
    if not validate_linkedin_connection(profile_dir):
        return jsonify({"success": False, "message": "No valid LinkedIn session found in browser_profile."}), 400
        
    jar = extract_cookies_from_browser(profile_dir)
    if not jar:
        return jsonify({"success": False, "message": "Failed to extract cookies from browser."}), 400
        
    cookies_dict = {cookie.name: cookie.value for cookie in jar}
    session_cookie = json.dumps(cookies_dict)
    
    from app.services.onboarding_service import save_linkedin_connection
    try:
        # Reuses the exact same encryption logic and DB update logic
        save_linkedin_connection(user_id, session_cookie)
        return jsonify({"success": True, "message": "LinkedIn session reconnected successfully."}), 200
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        import logging
        logging.error(f"Error reconnecting LinkedIn session: {e}")
        return jsonify({"success": False, "message": "Failed to save LinkedIn connection."}), 500


