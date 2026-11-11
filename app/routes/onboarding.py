import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from app.security.session import login_required
from app.security.limiter import limiter
from app.services.onboarding_service import (
    get_company, save_company, get_icp, save_icp, get_onboarding_status,
    get_optimization_settings, save_optimization_settings,
    get_linkedin_connection_status, save_linkedin_connection
)
from app.services.company_discovery_service import discover_company_for_user

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/api/onboarding')

@onboarding_bp.route('/company/identify', methods=['GET'])
@login_required
@limiter.limit("10 per minute")
def identify_company_domain():
    user_id = request.user_id
    try:
        result = discover_company_for_user(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except ValueError as ve:
        return jsonify({
            "success": False,
            "email_domain": None,
            "company_name": None,
            "official_website": None,
            "identification_status": "FAILED",
            "requires_user_confirmation": True,
            "message": str(ve)
        }), 400
    except Exception as e:
        logger.error(f"Error identifying company domain: {str(e)}")
        return jsonify({
            "success": False,
            "email_domain": None,
            "company_name": None,
            "official_website": None,
            "identification_status": "FAILED",
            "requires_user_confirmation": True,
            "message": "Unable to complete domain identification. Please enter details manually."
        }), 500


@onboarding_bp.route('/company/scrape', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def scrape_company_website():
    user_id = request.user_id
    data = request.get_json() or {}

    website_url = data.get("website_url")
    confirmed_by_user = bool(data.get("confirmed_by_user", False))
    identification_status = data.get("identification_status", "CONFIRMED")

    if not website_url:
        try:
            discovery_res = discover_company_for_user(user_id)
            if discovery_res.get("success") and discovery_res.get("official_website"):
                website_url = discovery_res["official_website"]
                identification_status = discovery_res.get("identification_status", "CONFIRMED")
                if "confirmed_by_user" not in data:
                    confirmed_by_user = not discovery_res.get("requires_user_confirmation", True)
            else:
                return jsonify({
                    "success": False,
                    "status": "FAILED",
                    "message": discovery_res.get("message", "No company website identified. Please enter website URL manually."),
                    "scraped_data": None
                }), 400
        except Exception as e:
            logger.error(f"Error discovering company for scrape endpoint: {str(e)}")
            return jsonify({
                "success": False,
                "status": "FAILED",
                "message": "Unable to discover company website. Please enter website URL manually.",
                "scraped_data": None
            }), 500

    try:
        from app.services.scraping_service import scrape_official_company_website

        result = scrape_official_company_website(
            website_url=website_url,
            identification_status=identification_status,
            requires_user_confirmation=(identification_status != "CONFIRMED"),
            confirmed_by_user=confirmed_by_user
        )

        status_code = 200 if result.get("status") in ("SUCCESS", "PARTIAL") else 400
        return jsonify({
            "success": result.get("status") in ("SUCCESS", "PARTIAL"),
            "status": result.get("status"),
            "scraped_data": result.get("scraped_data"),
            "source_urls": result.get("source_urls", []),
            "warnings": result.get("warnings", []),
            "message": result.get("message")
        }), status_code
    except Exception as e:
        logger.error(f"Error scraping company website: {str(e)}")
        return jsonify({
            "success": False,
            "status": "FAILED",
            "message": "An error occurred while extracting company details. Please try again or enter details manually.",
            "scraped_data": None
        }), 500


@onboarding_bp.route('/company', methods=['GET'])
@login_required
def get_company_details():
    user_id = request.user_id
    try:
        company = get_company(user_id)
        if not company:
            return jsonify({"success": True, "data": {}}), 200
        return jsonify({"success": True, "data": company}), 200
    except Exception as e:
        logger.error(f"Error fetching company details: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch company details"}), 500

@onboarding_bp.route('/company', methods=['POST', 'PUT'])
@login_required
def update_company_details():
    user_id = request.user_id
    data = request.get_json() or {}
    is_draft = bool(data.get("is_draft", False))

    try:
        company = save_company(user_id, data, is_draft=is_draft)
        return jsonify({"success": True, "data": company}), 200
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error saving company details: {str(e)}")
        return jsonify({"success": False, "message": "Unable to save company details. Please try again."}), 500


@onboarding_bp.route('/icp', methods=['GET'])
@login_required
def get_icp_details():
    user_id = request.user_id
    try:
        icp = get_icp(user_id)
        if not icp:
            return jsonify({"success": True, "data": {}}), 200
        return jsonify({"success": True, "data": icp}), 200
    except Exception as e:
        logger.error(f"Error fetching ICP details: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch ICP details"}), 500

@onboarding_bp.route('/icp', methods=['POST', 'PUT'])
@login_required
def update_icp_details():
    user_id = request.user_id
    data = request.get_json() or {}

    try:
        icp = save_icp(user_id, data)



        return jsonify({"success": True, "data": icp}), 200
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error saving ICP details: {str(e)}")
        return jsonify({"success": False, "message": "Unable to save ICP details. Please try again."}), 500


@onboarding_bp.route('/countries', methods=['GET'])
def get_countries():
    """
    Returns canonical countries, optionally filtered by search query.
    Used for location autocomplete suggestions.
    """
    from app.services.country_service import CANONICAL_COUNTRIES, search_countries
    query = (request.args.get('query') or request.args.get('q') or '').strip()
    if query:
        results = search_countries(query)
    else:
        results = CANONICAL_COUNTRIES
    return jsonify({"success": True, "countries": results}), 200


@onboarding_bp.route('/status', methods=['GET'])
@login_required
def get_status():
    user_id = request.user_id
    try:
        status = get_onboarding_status(user_id)
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Error fetching onboarding status: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch onboarding status"}), 500


@onboarding_bp.route('/optimization', methods=['GET'])
@login_required
def get_optimization_endpoint():
    user_id = request.user_id
    try:
        data = get_optimization_settings(user_id)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error fetching optimization settings: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch optimization settings"}), 500


@onboarding_bp.route('/optimization', methods=['POST', 'PUT'])
@login_required
def update_optimization_endpoint():
    user_id = request.user_id
    payload = request.get_json() or {}
    try:
        data = save_optimization_settings(user_id, payload)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error saving optimization settings: {str(e)}")
        return jsonify({"success": False, "message": "Failed to save optimization settings"}), 500


@onboarding_bp.route('/linkedin/status', methods=['GET'])
@login_required
def get_linkedin_status():
    user_id = request.user_id
    try:
        status = get_linkedin_connection_status(user_id)
        return jsonify({"success": True, "data": status}), 200
    except Exception as e:
        logger.error(f"Error fetching LinkedIn status: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch connection status"}), 500


@onboarding_bp.route('/linkedin/connect', methods=['POST'])
@login_required
def connect_linkedin():
    user_id = request.user_id
    data = request.get_json() or {}
    session_cookie = data.get("session_cookie", "").strip()

    if not session_cookie:
        return jsonify({"success": False, "message": "Session credential is required"}), 400

    try:
        status = save_linkedin_connection(user_id, session_cookie)
        return jsonify({"success": True, "data": status}), 200
    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error saving LinkedIn connection: {str(e)}")
        return jsonify({"success": False, "message": "Unable to connect LinkedIn. Please try again."}), 500


@onboarding_bp.route('/linkedin/verify-extension-session', methods=['POST'])
@login_required
def verify_extension_session():
    """
    Receives verification from the locally installed FameWeb Chrome extension.
    CRITICAL SECURITY: Does NOT accept, store, transmit, or log raw li_at cookies or passwords.
    Only accepts the verified status signal and updates UsersLinkedinDetails.
    """
    user_id = request.user_id
    data = request.get_json() or {}

    status_signal = data.get("status")  # 'CONNECTED', 'NOT_LOGGED_IN', 'VERIFICATION_FAILED'
    authenticated = bool(data.get("authenticated", False))
    profile_url = (data.get("profile_url") or "").strip()
    name = (data.get("name") or "").strip()

    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails, ConnectionStatus, UserTable
    from datetime import datetime

    try:
        linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if not linkedin:
            linkedin = UsersLinkedinDetails(user_id=user_id)
            db_session.add(linkedin)

        if status_signal == "CONNECTED" and authenticated:
            linkedin.connection_status = ConnectionStatus.CONNECTED.value
            linkedin.last_verified_at = datetime.utcnow()
            linkedin.profile_source = "CHROME_EXTENSION_LOCAL"
            if profile_url:
                linkedin.profile_url = profile_url
            if name:
                linkedin.name = name

            # Advance user onboarding step if pending
            user = db_session.query(UserTable).filter_by(user_id=user_id).first()
            if user and user.onboarding_step in ("LINKEDIN", "INTEGRATIONS"):
                user.onboarding_step = "COMPANY"

            db_session.commit()
            return jsonify({
                "success": True,
                "connected": True,
                "status": "CONNECTED",
                "message": "LinkedIn session verified successfully via FameWeb Chrome Extension.",
                "last_verified_at": linkedin.last_verified_at.isoformat()
            }), 200
        else:
            linkedin.connection_status = ConnectionStatus.DISCONNECTED.value
            db_session.commit()
            return jsonify({
                "success": True,
                "connected": False,
                "status": status_signal or "NOT_LOGGED_IN",
                "message": "LinkedIn is not currently logged in in your browser."
            }), 200

    except Exception as e:
        db_session.rollback()
        logger.error(f"[Onboarding LinkedIn] Error saving extension verification: {e}")
        return jsonify({"success": False, "message": "Failed to update LinkedIn verification status."}), 500


@onboarding_bp.route('/integrations/status', methods=['GET'])
@login_required
def get_integrations_status():
    """
    Returns current onboarding integration statuses (SMTP and LinkedIn)
    for the authenticated user. Never exposes passwords or sensitive credentials.
    """
    user_id = request.user_id
    from app.database import db_session
    from app.models.all_models import UserSMTPAccount, UsersLinkedinDetails, ConnectionStatus

    # 1. SMTP Account status
    smtp_acc = db_session.query(UserSMTPAccount).filter_by(user_id=user_id, is_primary=True).first()
    if not smtp_acc:
        smtp_acc = db_session.query(UserSMTPAccount).filter_by(user_id=user_id).order_by(UserSMTPAccount.created_at.desc()).first()

    smtp_data = {
        "configured": bool(smtp_acc),
        "email_address": smtp_acc.email_address if smtp_acc else None,
        "smtp_host": smtp_acc.smtp_host if smtp_acc else None,
        "smtp_port": smtp_acc.smtp_port if smtp_acc else None,
        "smtp_username": smtp_acc.smtp_username if smtp_acc else None,
        "use_tls": smtp_acc.use_tls if smtp_acc else True,
        "use_ssl": smtp_acc.use_ssl if smtp_acc else False,
        "connection_status": smtp_acc.connection_status if smtp_acc else "PENDING",
        "last_tested_at": smtp_acc.last_tested_at.isoformat() if smtp_acc and smtp_acc.last_tested_at else None
    }

    # 2. LinkedIn status
    linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    is_li_connected = bool(linkedin and linkedin.connection_status == ConnectionStatus.CONNECTED.value)

    linkedin_data = {
        "connected": is_li_connected,
        "status": linkedin.connection_status if linkedin else ConnectionStatus.DISCONNECTED.value,
        "profile_url": linkedin.profile_url if linkedin else None,
        "name": linkedin.name if linkedin else None,
        "last_verified_at": linkedin.last_verified_at.isoformat() if linkedin and linkedin.last_verified_at else None,
        "profile_source": linkedin.profile_source if linkedin else None
    }

    return jsonify({
        "success": True,
        "smtp": smtp_data,
        "linkedin": linkedin_data
    }), 200


@onboarding_bp.route('/linkedin/disconnect', methods=['POST'])
@login_required
def disconnect_linkedin():
    user_id = request.user_id
    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails, ConnectionStatus
    try:
        linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if linkedin:
            linkedin.connection_status = ConnectionStatus.DISCONNECTED.value
            linkedin.auth_data_encrypted = None
            db_session.commit()
        return jsonify({"success": True, "data": {"connected": False, "status": ConnectionStatus.DISCONNECTED.value}}), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error disconnecting LinkedIn: {str(e)}")
        return jsonify({"success": False, "message": "Failed to disconnect"}), 500


@onboarding_bp.route('/profile/import-extension', methods=['POST'])
@login_required
def import_extension_profile():
    """
    Receives user-consented, sanitized own-profile data extracted by the FameWeb Chrome extension.
    CRITICAL SECURITY & COMPLIANCE:
    - Never accepts, logs, or stores cookies, tokens, or credentials.
    - Validates payload structure and field limits.
    - Persists cleanly into UsersLinkedinDetails without external APIs.
    """
    user_id = request.user_id
    data = request.get_json(silent=True)

    if not data or not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "INVALID_PAYLOAD",
            "message": "Valid JSON profile payload is required."
        }), 400

    profile = data.get("profile") or data.get("data") or data
    if not isinstance(profile, dict):
        return jsonify({
            "success": False,
            "error": "MISSING_PROFILE_DATA",
            "message": "Payload must include a structured 'profile' or 'data' object."
        }), 400

    # Sanitize helper
    def clean_str(val, max_len=1000):
        if val is None:
            return None
        s = str(val).strip()
        return s[:max_len] if s else None

    # Validate essential identity fields
    name = clean_str(profile.get("name"), 200)
    headline = clean_str(profile.get("headline"), 500)

    if not name and not headline:
        return jsonify({
            "success": False,
            "error": "INSUFFICIENT_IDENTITY",
            "message": "Imported profile must at least include a visible name or headline."
        }), 400

    from app.database import db_session
    from app.models.all_models import UsersLinkedinDetails, ConnectionStatus

    try:
        linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
        if not linkedin:
            linkedin = UsersLinkedinDetails(user_id=user_id)
            db_session.add(linkedin)

        if name:
            linkedin.name = name
        if headline:
            linkedin.headline = headline

        about = clean_str(profile.get("about"), 4000)
        if about:
            linkedin.about = about

        location = clean_str(profile.get("location"), 200)
        if location:
            linkedin.location = location

        current_pos = clean_str(profile.get("current_position"), 300)
        if current_pos:
            linkedin.current_position = current_pos

        profile_url = clean_str(profile.get("profile_url"), 500)
        if profile_url and "linkedin.com" in profile_url:
            linkedin.profile_url = profile_url

        vanity_name = clean_str(profile.get("vanity_name"), 100)
        if vanity_name:
            linkedin.linkedin_id = vanity_name

        # Experience (sanitized list of dicts)
        raw_exp = profile.get("experience")
        clean_exp = []
        if isinstance(raw_exp, list):
            for item in raw_exp[:25]:  # Reasonable limit
                if isinstance(item, dict):
                    clean_exp.append({
                        "title": clean_str(item.get("title"), 200) or "",
                        "company": clean_str(item.get("company"), 200) or "",
                        "start_date": clean_str(item.get("start_date") or item.get("dates"), 100) or "",
                        "location": clean_str(item.get("location"), 150) or "",
                        "description": clean_str(item.get("description"), 2000) or ""
                    })
        if clean_exp:
            linkedin.experience = clean_exp

        # Education (sanitized list of dicts)
        raw_edu = profile.get("education")
        clean_edu = []
        if isinstance(raw_edu, list):
            for item in raw_edu[:15]:
                if isinstance(item, dict):
                    clean_edu.append({
                        "school": clean_str(item.get("school"), 200) or "",
                        "degree": clean_str(item.get("degree"), 200) or "",
                        "field_of_study": clean_str(item.get("field_of_study"), 200) or "",
                        "dates": clean_str(item.get("dates"), 100) or ""
                    })
        if clean_edu:
            linkedin.education = clean_edu

        # Skills (list of strings)
        raw_skills = profile.get("skills")
        clean_skills = []
        if isinstance(raw_skills, list):
            for s in raw_skills[:100]:
                cleaned = clean_str(s, 100)
                if cleaned and cleaned not in clean_skills:
                    clean_skills.append(cleaned)
        if clean_skills:
            linkedin.skills = clean_skills

        # Certifications (sanitized list of dicts or strings)
        raw_certs = profile.get("certifications")
        clean_certs = []
        if isinstance(raw_certs, list):
            for c in raw_certs[:25]:
                if isinstance(c, dict):
                    clean_certs.append({
                        "name": clean_str(c.get("name"), 200) or "",
                        "authority": clean_str(c.get("authority"), 200) or "",
                        "issued": clean_str(c.get("issued"), 100) or ""
                    })
                elif isinstance(c, str) and c.strip():
                    clean_certs.append({
                        "name": clean_str(c, 200),
                        "authority": "",
                        "issued": ""
                    })

        # Profile photo url and rich fields into profile_data JSONB
        existing_pdata = dict(linkedin.profile_data or {})
        photo_url = clean_str(profile.get("profile_photo_url"), 1000)
        if photo_url:
            existing_pdata["profile_photo_url"] = photo_url
        if clean_certs:
            existing_pdata["certifications"] = clean_certs

        # Store metadata
        raw_meta = data.get("metadata") or {}
        existing_pdata["last_imported_via"] = "CHROME_EXTENSION_DOM"
        existing_pdata["imported_at"] = datetime.utcnow().isoformat()
        if isinstance(raw_meta, dict):
            existing_pdata["extraction_warnings"] = raw_meta.get("warnings", [])

        # Determine completeness honestly
        substantive_count = sum([
            1 if clean_exp else 0,
            1 if clean_edu else 0,
            1 if clean_skills else 0,
            1 if about else 0
        ])
        profile_completeness_status = "complete" if substantive_count >= 2 else ("partial" if (name or headline) else "insufficient")
        existing_pdata["completeness_status"] = profile_completeness_status
        linkedin.profile_completeness = profile_completeness_status

        linkedin.profile_data = existing_pdata
        linkedin.profile_source = "CHROME_EXTENSION_DOM"
        linkedin.connection_status = ConnectionStatus.CONNECTED.value
        linkedin.last_verified_at = datetime.utcnow()

        db_session.commit()

        imported_sections = []
        if name: imported_sections.append("name")
        if headline: imported_sections.append("headline")
        if about: imported_sections.append("about")
        if location: imported_sections.append("location")
        if clean_exp: imported_sections.append("experience")
        if clean_edu: imported_sections.append("education")
        if clean_skills: imported_sections.append("skills")
        if clean_certs: imported_sections.append("certifications")

        warnings_list = raw_meta.get("warnings", []) if isinstance(raw_meta, dict) else []

        return jsonify({
            "success": True,
            "message": "LinkedIn profile successfully imported from active browser session.",
            "import_status": profile_completeness_status,
            "sections_imported": imported_sections,
            "experience_count": len(clean_exp),
            "education_count": len(clean_edu),
            "skills_count": len(clean_skills),
            "certifications_count": len(clean_certs),
            "has_about": bool(linkedin.about),
            "warnings": warnings_list,
            "data": {
                "name": linkedin.name,
                "headline": linkedin.headline,
                "about": bool(linkedin.about),
                "location": linkedin.location,
                "current_position": linkedin.current_position,
                "experience_count": len(clean_exp),
                "education_count": len(clean_edu),
                "skills_count": len(clean_skills),
                "certifications_count": len(clean_certs),
                "sections_imported": len(imported_sections),
                "import_status": profile_completeness_status,
                "warnings": warnings_list
            }
        }), 200

    except Exception as e:
        db_session.rollback()
        logger.error(f"[Profile Import] Error importing profile for user {user_id}: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "IMPORT_FAILED",
            "message": f"Failed to save imported profile: {str(e)}"
        }), 500

