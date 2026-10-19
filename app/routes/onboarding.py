import logging
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
