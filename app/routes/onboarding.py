import logging
from flask import Blueprint, request, jsonify
from app.security.session import login_required
from app.services.onboarding_service import (
    get_company, save_company, get_icp, save_icp, get_onboarding_status
)

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/api/onboarding')

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
    
    try:
        company = save_company(user_id, data)
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
