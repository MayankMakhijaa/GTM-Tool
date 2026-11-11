import logging
from typing import Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, request, jsonify, session
from sqlalchemy import or_, and_, func, desc, case
from app.database import db_session
from app.models.all_models import (
    UserTable,
    UserRole,
    UsersCompanyDetails,
    UsersICP,
    GlobalProfiles,
    UsersProfiles,
    AuditLog,
    AIProviderUsageLog
)
from app.security.session import super_admin_required
from app.services.onboarding_service import validate_icp_data, get_icp
from app.services.auth_service import signup_user
from app.services.otp_service import create_and_send_otp

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def safe_dt_iso(dt_val: Any, suffix: str = "") -> Optional[str]:
    """Helper to safely format a model datetime attribute or None to ISO-8601 string."""
    if dt_val is not None and hasattr(dt_val, "isoformat"):
        return dt_val.isoformat() + suffix
    return None

@admin_bp.route('/overview', methods=['GET'])
@super_admin_required
def admin_overview():
    """
    Returns high-level system metrics computed directly using database counts.
    """
    try:
        total_users = db_session.query(func.count(UserTable.user_id)).scalar() or 0
        active_users = db_session.query(func.count(UserTable.user_id)).filter(UserTable.is_active == True).scalar() or 0
        total_global_profiles = db_session.query(func.count(GlobalProfiles.global_id)).scalar() or 0
        total_user_lead_associations = db_session.query(func.count(UsersProfiles.id)).scalar() or 0

        return jsonify({
            "success": True,
            "metrics": {
                "total_users": total_users,
                "active_users": active_users,
                "total_global_profiles": total_global_profiles,
                "total_user_lead_associations": total_user_lead_associations
            }
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN] Error computing overview metrics: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to load metrics."}), 500


@admin_bp.route('/users', methods=['GET'])
@super_admin_required
def list_users():
    """
    Returns a paginated list of users with optional filtering and search.
    Never exposes passwords, OTPs, or encrypted credentials.
    """
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 20))))
        search = (request.args.get('search') or '').strip()
        role_filter = (request.args.get('role') or '').strip()
        is_active_filter = request.args.get('is_active')

        query = db_session.query(UserTable)

        if search:
            search_pat = f"%{search}%"
            query = query.filter(or_(
                UserTable.name.ilike(search_pat),
                UserTable.email_id.ilike(search_pat),
                UserTable.phone_no.ilike(search_pat)
            ))

        if role_filter:
            query = query.filter(UserTable.role == role_filter)

        if is_active_filter is not None and is_active_filter != '':
            active_bool = is_active_filter.lower() in ('true', '1', 'yes')
            query = query.filter(UserTable.is_active == active_bool)

        total = query.count()
        users = query.order_by(UserTable.user_id.desc()).offset((page - 1) * limit).limit(limit).all()

        user_list = []
        for u in users:
            user_list.append({
                "user_id": u.user_id,
                "name": u.name,
                "email_id": u.email_id,
                "phone_no": u.phone_no,
                "role": u.role,
                "is_active": u.is_active,
                "email_verified": getattr(u, 'email_verified_at', None) is not None,
                "email_verified_at": safe_dt_iso(getattr(u, 'email_verified_at', None)),
                "onboarding_step": u.onboarding_step,
                "optimization_status": u.optimization_status,
                "created_at": safe_dt_iso(getattr(u, 'created_at', None))
            })

        return jsonify({
            "success": True,
            "total": total,
            "page": page,
            "limit": limit,
            "users": user_list
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN] Error listing users: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to list users."}), 500


@admin_bp.route('/users/<int:target_user_id>', methods=['GET'])
@super_admin_required
def get_user_details(target_user_id: int):
    """
    Fetches full user account info, company details, and saved ICP.
    Safe: zero secrets returned.
    """
    try:
        user = db_session.query(UserTable).filter_by(user_id=target_user_id).first()
        if not user:
            return jsonify({"success": False, "error": "User not found."}), 404

        company = db_session.query(UsersCompanyDetails).filter_by(user_id=target_user_id).first()
        icp = db_session.query(UsersICP).filter_by(user_id=target_user_id).first()

        company_dict = None
        if company:
            company_dict = {
                "id": company.id,
                "company_name": company.company_name,
                "website_url": company.website_url,
                "description": company.description,
                "what_company_sells": company.what_company_sells,
                "products_services": company.products_services,
                "industry": company.industry,
                "company_size": company.company_size,
                "revenue": company.revenue,
                "location": company.location,
                "rating": company.rating,
                "scrape_status": company.scrape_status
            }

        icp_dict = None
        if icp:
            icp_dict = {
                "id": icp.id,
                "target_customer": icp.target_customer,
                "company_size": icp.company_size,
                "revenue_range": icp.revenue_range,
                "target_jobs_roles": icp.target_jobs_roles,
                "industry": icp.industry,
                "location": icp.location,
                "keywords": icp.keywords,
                "exclusions": icp.exclusions,
                "signals": icp.signals,
                "tone": icp.tone,
                "version": icp.version,
                "summary_report": icp.summary_report,
                "updated_at": safe_dt_iso(getattr(icp, 'updated_at', None))
            }

        return jsonify({
            "success": True,
            "user": {
                "user_id": user.user_id,
                "name": user.name,
                "email_id": user.email_id,
                "phone_no": user.phone_no,
                "role": user.role,
                "is_active": user.is_active,
                "email_verified": getattr(user, 'email_verified_at', None) is not None,
                "email_verified_at": safe_dt_iso(getattr(user, 'email_verified_at', None)),
                "onboarding_step": user.onboarding_step,
                "optimization_status": user.optimization_status,
                "created_at": safe_dt_iso(getattr(user, 'created_at', None))
            },
            "company": company_dict,
            "icp": icp_dict
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN] Error fetching user {target_user_id} details: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to fetch user details."}), 500


@admin_bp.route('/users/<int:target_user_id>/status', methods=['PUT', 'PATCH'])
@super_admin_required
def update_user_status(target_user_id: int):
    """
    Activates or deactivates a user account.
    Prevents self-deactivation or deactivation of the last remaining active SUPER_ADMIN.
    """
    admin_id = session.get('user_id')
    data = request.get_json() or {}
    new_active_status = data.get('is_active')

    if new_active_status is None:
        return jsonify({"success": False, "error": "is_active boolean is required."}), 400

    new_active_status = bool(new_active_status)

    target_user = db_session.query(UserTable).filter_by(user_id=target_user_id).first()
    if not target_user:
        return jsonify({"success": False, "error": "User not found."}), 404

    # Protection: Prevent admin from deactivating themselves
    if target_user.user_id == admin_id and not new_active_status:
        return jsonify({
            "success": False,
            "error": "SELF_DEACTIVATION_BLOCKED",
            "message": "You cannot deactivate your own administrative account."
        }), 400

    target_role = getattr(target_user, 'role', None)
    # Protection: Prevent deactivation of the last active SUPER_ADMIN
    if target_role == UserRole.SUPER_ADMIN.value and not new_active_status:
        active_super_admins = db_session.query(func.count(UserTable.user_id)).filter(
            UserTable.role == UserRole.SUPER_ADMIN.value,
            UserTable.is_active == True
        ).scalar() or 0
        if active_super_admins <= 1:
            return jsonify({
                "success": False,
                "error": "LAST_SUPER_ADMIN_BLOCKED",
                "message": "Cannot deactivate the last active Super Administrator."
            }), 400

    old_status = getattr(target_user, 'is_active', None)
    setattr(target_user, 'is_active', new_active_status)
    setattr(target_user, 'updated_at', datetime.utcnow())

    # Log administrative action
    action = "USER_REACTIVATED" if new_active_status else "USER_DEACTIVATED"
    audit = AuditLog(
        admin_user_id=admin_id,
        target_user_id=target_user_id,
        action=action,
        metadata_json={
            "old_is_active": old_status,
            "new_is_active": new_active_status
        }
    )
    db_session.add(audit)

    try:
        db_session.commit()
        return jsonify({
            "success": True,
            "message": f"User account {'reactivated' if new_active_status else 'deactivated'} successfully.",
            "user_id": target_user.user_id,
            "is_active": target_user.is_active
        }), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"[ADMIN] Error updating user status: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Database error updating user status."}), 500


@admin_bp.route('/users/<int:target_user_id>', methods=['DELETE'])
@super_admin_required
def delete_user(target_user_id: int):
    """
    Permanently deletes a user account with Superadmin authorization.
    Safeguards:
    - Admin cannot delete themselves.
    - Cannot delete the last active SUPER_ADMIN.
    - Cleans up associated user data across tables safely.
    - Records audit log.
    """
    admin_id = session.get('user_id')
    target_user = db_session.query(UserTable).filter_by(user_id=target_user_id).first()
    if not target_user:
        return jsonify({"success": False, "error": "User not found."}), 404

    # Protection: Prevent admin from deleting themselves
    if target_user.user_id == admin_id:
        return jsonify({
            "success": False,
            "error": "SELF_DELETION_BLOCKED",
            "message": "You cannot delete your own administrative account."
        }), 400

    # Protection: Prevent deleting last active SUPER_ADMIN
    target_role = getattr(target_user, 'role', None)
    if target_role == UserRole.SUPER_ADMIN.value:
        active_super_admins = db_session.query(func.count(UserTable.user_id)).filter(
            UserTable.role == UserRole.SUPER_ADMIN.value,
            UserTable.is_active == True
        ).scalar() or 0
        if active_super_admins <= 1 and target_user.is_active:
            return jsonify({
                "success": False,
                "error": "LAST_SUPER_ADMIN_BLOCKED",
                "message": "Cannot delete the last active Super Administrator."
            }), 400

    deleted_user_email = target_user.email_id
    deleted_user_name = target_user.name

    try:
        from app.models.all_models import (
            UsersCompanyDetails, UsersICP, UsersLinkedinDetails,
            UsersProfiles, ResearchJobs, ConnectAndMessage, EmailVerificationOTP,
            CreditTransaction, CreditReservation, UserCreditWallet,
            AIProviderUsageLog, TenantMembership, UserSMTPAccount,
            EmailBatch, EmailRecipient
        )

        # 1. Clear out dependent child records without CASCADE or with RESTRICT
        db_session.query(UsersCompanyDetails).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(UsersICP).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(UsersLinkedinDetails).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(UsersProfiles).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(ConnectAndMessage).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(EmailVerificationOTP).filter_by(user_id=target_user_id).delete(synchronize_session=False)

        # Bulk email & SMTP
        db_session.query(EmailRecipient).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(EmailBatch).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(UserSMTPAccount).filter_by(user_id=target_user_id).delete(synchronize_session=False)

        # Credit transactions & reservations & wallet
        db_session.query(CreditTransaction).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(CreditReservation).filter_by(user_id=target_user_id).delete(synchronize_session=False)
        db_session.query(UserCreditWallet).filter_by(user_id=target_user_id).delete(synchronize_session=False)

        # Tenant memberships
        db_session.query(TenantMembership).filter_by(user_id=target_user_id).delete(synchronize_session=False)

        # Research jobs
        db_session.query(ResearchJobs).filter_by(user_id=target_user_id).delete(synchronize_session=False)

        # AI logs
        db_session.query(AIProviderUsageLog).filter_by(user_id=target_user_id).delete(synchronize_session=False)

        # Anonymize or unlink any audit log entries where target was the admin or target
        db_session.query(AuditLog).filter_by(target_user_id=target_user_id).update({AuditLog.target_user_id: None}, synchronize_session=False)
        db_session.query(AuditLog).filter_by(admin_user_id=target_user_id).update({AuditLog.admin_user_id: None}, synchronize_session=False)

        # Record deletion audit log before deleting user
        audit = AuditLog(
            admin_user_id=admin_id,
            target_user_id=None,
            action="USER_DELETED",
            metadata_json={
                "deleted_user_id": target_user_id,
                "deleted_user_email": deleted_user_email,
                "deleted_user_name": deleted_user_name,
                "deleted_user_role": target_role
            }
        )
        db_session.add(audit)

        # Delete the user record
        db_session.delete(target_user)
        db_session.commit()

        return jsonify({
            "success": True,
            "message": f"User account '{deleted_user_name}' ({deleted_user_email}) has been permanently deleted.",
            "user_id": target_user_id
        }), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"[ADMIN] Error deleting user {target_user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Database error deleting user."}), 500


@admin_bp.route('/users/<int:target_user_id>/icp', methods=['PUT'])
@super_admin_required
def admin_update_user_icp(target_user_id: int):
    """
    Allows Super Admin to edit a customer's ICP using standard validation rules,
    incrementing version if qualification fields change, and recording an audit log.
    """
    admin_id = session.get('user_id')
    target_user = db_session.query(UserTable).filter_by(user_id=target_user_id).first()
    if not target_user:
        return jsonify({"success": False, "error": "User not found."}), 404

    payload = request.get_json() or {}

    try:
        valid_data = validate_icp_data(payload)
    except ValueError as ve:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": str(ve)}), 400

    icp = db_session.query(UsersICP).filter_by(user_id=target_user_id).first()
    is_new = False
    if not icp:
        icp = UsersICP(user_id=target_user_id, version=1)
        db_session.add(icp)
        is_new = True

    qualification_fields = [
        'target_customer', 'company_size', 'revenue_range',
        'target_jobs_roles', 'industry', 'location',
        'keywords', 'exclusions', 'signals'
    ]

    requires_version_bump = False
    raw_old_ver = getattr(icp, 'version', None)
    old_version: int = int(raw_old_ver) if raw_old_ver is not None else 1
    diff = {}

    for key, value in valid_data.items():
        old_val = getattr(icp, key, None)
        if not is_new and key in qualification_fields:
            if old_val != value:
                requires_version_bump = True
                diff[key] = {"old": old_val, "new": value}
        setattr(icp, key, value)

    if requires_version_bump:
        setattr(icp, 'version', old_version + 1)
    setattr(icp, 'updated_at', datetime.utcnow())

    # Log audit entry
    audit = AuditLog(
        admin_user_id=admin_id,
        target_user_id=target_user_id,
        action="ADMIN_EDIT_ICP",
        metadata_json={
            "old_version": old_version,
            "new_version": icp.version,
            "modified_fields": list(diff.keys())
        }
    )
    db_session.add(audit)

    try:
        db_session.commit()
        return jsonify({
            "success": True,
            "message": "ICP updated successfully by administrator.",
            "icp": get_icp(target_user_id)
        }), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"[ADMIN] Error updating ICP: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Database error saving ICP."}), 500


@admin_bp.route('/users/create', methods=['POST'])
@super_admin_required
def admin_create_user():
    """
    Allows Super Admin to provision a new customer account safely without bypassing
    password hashing or email verification standards. Sends verification OTP to the user.
    """
    admin_id = session.get('user_id')
    data = request.get_json() or {}
    name = str(data.get('name') or '').strip()
    email = str(data.get('email') or '').strip()
    phone = str(data.get('phone') or '').strip()
    password = str(data.get('password') or '').strip()

    if not name or not email or not phone or not password:
        return jsonify({
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Name, email, phone, and password are all required."
        }), 400

    try:
        new_user = signup_user(name, email, phone, password)
        # Send verification OTP to the customer
        create_and_send_otp(new_user)

        audit = AuditLog(
            admin_user_id=admin_id,
            target_user_id=new_user.user_id,
            action="ADMIN_PROVISION_USER",
            metadata_json={
                "email": new_user.email_id,
                "phone": new_user.phone_no
            }
        )
        db_session.add(audit)
        db_session.commit()

        return jsonify({
            "success": True,
            "message": "Customer account provisioned successfully. Verification email sent.",
            "user": {
                "user_id": new_user.user_id,
                "name": new_user.name,
                "email_id": new_user.email_id,
                "role": new_user.role,
                "is_active": new_user.is_active
            }
        }), 201
    except ValueError as ve:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": str(ve)}), 400
    except Exception as e:
        db_session.rollback()
        logger.error(f"[ADMIN] Error provisioning user: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================================
# Ticket 3C: Super Admin Credit & Pricing Management Endpoints
# ==============================================================================

@admin_bp.route('/credits/overview', methods=['GET'])
@super_admin_required
def get_credit_overview():
    """
    Returns aggregated credit system metrics and active feature pricing.
    Computes totals directly via DB aggregation without iterating user transaction logs.
    """
    from decimal import Decimal
    from app.models.all_models import UserCreditWallet, FeaturePricing

    try:
        total_wallets = db_session.query(func.count(UserCreditWallet.user_id)).scalar() or 0
        total_balance_sum = db_session.query(func.coalesce(func.sum(UserCreditWallet.total_balance), Decimal("0.00"))).scalar()
        reserved_balance_sum = db_session.query(func.coalesce(func.sum(UserCreditWallet.reserved_balance), Decimal("0.00"))).scalar()
        available_balance_sum = (total_balance_sum - reserved_balance_sum).quantize(Decimal("0.01"))

        active_pricing = db_session.query(FeaturePricing).filter_by(is_active=True).all()
        pricing_list = []
        for p in active_pricing:
            pricing_list.append({
                "feature_code": p.feature_code,
                "name": p.name,
                "description": p.description,
                "unit_name": p.unit_name,
                "credit_cost": str(p.credit_cost),
                "is_active": p.is_active,
                "version": p.version,
                "updated_at": safe_dt_iso(getattr(p, 'updated_at', None))
            })

        return jsonify({
            "success": True,
            "metrics": {
                "wallets_count": total_wallets,
                "total_balance": str(total_balance_sum),
                "reserved_balance": str(reserved_balance_sum),
                "available_balance": str(available_balance_sum),
                "active_pricing_count": len(pricing_list)
            },
            "pricing": pricing_list
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_CREDITS] Error fetching credit overview: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to load credit overview."}), 500


@admin_bp.route('/credits/users', methods=['GET'])
@super_admin_required
def list_credit_users():
    """
    Returns paginated user list with credit balances using a LEFT OUTER JOIN
    so users without wallets are visible with 0.00 balances without inserting rows.
    Supports filtering by search query, account status, and nonzero balance.
    """
    from decimal import Decimal
    from app.models.all_models import UserCreditWallet

    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 15))))
        search = (request.args.get('search') or '').strip()
        status_filter = (request.args.get('status') or '').strip() # 'active', 'inactive'
        nonzero_only = (request.args.get('nonzero_only') or '').lower() in ('true', '1', 'yes')

        query = db_session.query(
            UserTable.user_id,
            UserTable.name,
            UserTable.email_id,
            UserTable.role,
            UserTable.is_active,
            func.coalesce(UserCreditWallet.total_balance, Decimal("0.00")).label("total_balance"),
            func.coalesce(UserCreditWallet.reserved_balance, Decimal("0.00")).label("reserved_balance"),
            (func.coalesce(UserCreditWallet.total_balance, Decimal("0.00")) - func.coalesce(UserCreditWallet.reserved_balance, Decimal("0.00"))).label("available_balance")
        ).outerjoin(UserCreditWallet, UserTable.user_id == UserCreditWallet.user_id)

        if search:
            search_pat = f"%{search}%"
            query = query.filter(or_(
                UserTable.name.ilike(search_pat),
                UserTable.email_id.ilike(search_pat)
            ))

        if status_filter:
            if status_filter == 'active':
                query = query.filter(UserTable.is_active == True)
            elif status_filter == 'inactive':
                query = query.filter(UserTable.is_active == False)

        if nonzero_only:
            query = query.filter(func.coalesce(UserCreditWallet.total_balance, Decimal("0.00")) > Decimal("0.00"))

        total_count = query.count()
        rows = query.order_by(UserTable.user_id.desc()).offset((page - 1) * limit).limit(limit).all()

        users_data = []
        for r in rows:
            users_data.append({
                "user_id": r.user_id,
                "name": r.name,
                "email_id": r.email_id,
                "role": r.role,
                "is_active": r.is_active,
                "total_balance": str(r.total_balance),
                "reserved_balance": str(r.reserved_balance),
                "available_balance": str(r.available_balance)
            })

        return jsonify({
            "success": True,
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit,
            "users": users_data
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_CREDITS] Error listing credit users: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to list credit users."}), 500


@admin_bp.route('/credits/users/<int:user_id>', methods=['GET'])
@super_admin_required
def get_user_credit_details(user_id: int):
    """
    Returns single user's wallet balances and status.
    """
    from decimal import Decimal
    from app.services.credit_service import CreditService

    target_user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if not target_user:
        return jsonify({"success": False, "error": "NOT_FOUND", "message": f"User {user_id} not found."}), 404

    try:
        balance_info = CreditService.get_wallet_balance(user_id)
        return jsonify({
            "success": True,
            "user": {
                "user_id": target_user.user_id,
                "name": target_user.name,
                "email_id": target_user.email_id,
                "role": target_user.role,
                "is_active": target_user.is_active
            },
            "wallet": {
                "total_balance": str(balance_info["total_balance"]),
                "reserved_balance": str(balance_info["reserved_balance"]),
                "available_balance": str(balance_info["available_balance"])
            }
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_CREDITS] Error fetching user credit details for {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to load wallet details."}), 500


@admin_bp.route('/credits/users/<int:user_id>/grant', methods=['POST'])
@super_admin_required
def admin_grant_credits(user_id: int):
    """
    Super Admin endpoint to grant credits to a customer.
    Requires amount > 0, non-blank reason, and stable idempotency_key.
    Uses CreditService.grant_credits and records AuditLog.
    """
    from app.services.credit_service import CreditService, IdempotencyConflictError

    admin_id = session.get('user_id')
    target_user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if not target_user:
        return jsonify({"success": False, "error": "NOT_FOUND", "message": f"User {user_id} not found."}), 404

    data = request.get_json() or {}
    amount = data.get('amount')
    reason = (data.get('reason') or '').strip()
    idempotency_key = (data.get('idempotency_key') or '').strip()

    if not reason:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "A non-blank reason is required."}), 400

    if not idempotency_key or len(idempotency_key) > 160:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "idempotency_key is required and must not exceed 160 characters."}), 400

    try:
        result = CreditService.grant_credits(
            user_id=user_id,
            amount=amount,
            idempotency_key=idempotency_key,
            reason=reason,
            actor_user_id=admin_id,
            metadata={"admin_action": "ADMIN_CREDIT_GRANT", "admin_user_id": admin_id}
        )

        # Audit log (avoid duplicating on idempotent replay)
        if not result.get("is_idempotent_replay"):
            audit = AuditLog(
                admin_user_id=admin_id,
                target_user_id=user_id,
                action="ADMIN_GRANT_CREDITS",
                metadata_json={
                    "amount": str(result["amount"]),
                    "balance_after": str(result["balance_after"]),
                    "idempotency_key": idempotency_key,
                    "reason": reason
                }
            )
            db_session.add(audit)
            db_session.commit()

        return jsonify({
            "success": True,
            "message": "Credits granted successfully.",
            "transaction_id": result["transaction_id"],
            "amount": str(result["amount"]),
            "balance_after": str(result["balance_after"]),
            "reserved_after": str(result["reserved_after"]),
            "is_idempotent_replay": result["is_idempotent_replay"]
        }), 200
    except IdempotencyConflictError as ice:
        return jsonify({"success": False, "error": "IDEMPOTENCY_CONFLICT", "message": str(ice)}), 409
    except ValueError as ve:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": str(ve)}), 400
    except Exception as e:
        logger.error(f"[ADMIN_CREDITS] Unexpected error granting credits to user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to grant credits."}), 500


@admin_bp.route('/credits/users/<int:user_id>/adjust', methods=['POST'])
@super_admin_required
def admin_adjust_credits(user_id: int):
    """
    Super Admin endpoint to adjust credits (signed amount, positive or negative).
    Negative adjustments are rejected if total_balance < reserved_balance.
    Requires amount != 0, non-blank reason, and stable idempotency_key.
    """
    from app.services.credit_service import CreditService, IdempotencyConflictError

    admin_id = session.get('user_id')
    target_user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if not target_user:
        return jsonify({"success": False, "error": "NOT_FOUND", "message": f"User {user_id} not found."}), 404

    data = request.get_json() or {}
    amount = data.get('amount')
    reason = (data.get('reason') or '').strip()
    idempotency_key = (data.get('idempotency_key') or '').strip()

    if not reason:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "A non-blank reason is required."}), 400

    if not idempotency_key or len(idempotency_key) > 160:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "idempotency_key is required and must not exceed 160 characters."}), 400

    try:
        result = CreditService.adjust_credits(
            user_id=user_id,
            amount=amount,
            idempotency_key=idempotency_key,
            reason=reason,
            actor_user_id=admin_id,
            metadata={"admin_action": "ADMIN_CREDIT_ADJUSTMENT", "admin_user_id": admin_id}
        )

        if not result.get("is_idempotent_replay"):
            audit = AuditLog(
                admin_user_id=admin_id,
                target_user_id=user_id,
                action="ADMIN_ADJUST_CREDITS",
                metadata_json={
                    "amount": str(result["amount"]),
                    "balance_after": str(result["balance_after"]),
                    "idempotency_key": idempotency_key,
                    "reason": reason
                }
            )
            db_session.add(audit)
            db_session.commit()

        return jsonify({
            "success": True,
            "message": "Credits adjusted successfully.",
            "transaction_id": result["transaction_id"],
            "amount": str(result["amount"]),
            "balance_after": str(result["balance_after"]),
            "reserved_after": str(result["reserved_after"]),
            "is_idempotent_replay": result["is_idempotent_replay"]
        }), 200
    except IdempotencyConflictError as ice:
        return jsonify({"success": False, "error": "IDEMPOTENCY_CONFLICT", "message": str(ice)}), 409
    except ValueError as ve:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": str(ve)}), 400
    except Exception as e:
        logger.error(f"[ADMIN_CREDITS] Unexpected error adjusting credits for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to adjust credits."}), 500


@admin_bp.route('/credits/users/<int:user_id>/transactions', methods=['GET'])
@super_admin_required
def get_user_transactions(user_id: int):
    """
    Returns paginated transaction history from the append-only ledger for a user.
    Supports filtering by transaction_type and date range.
    """
    from app.models.all_models import CreditTransaction

    target_user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if not target_user:
        return jsonify({"success": False, "error": "NOT_FOUND", "message": f"User {user_id} not found."}), 404

    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 20))))
        tx_type = (request.args.get('type') or '').strip()

        query = db_session.query(CreditTransaction).filter_by(user_id=user_id)

        if tx_type:
            query = query.filter(CreditTransaction.transaction_type == tx_type)

        total_count = query.count()
        txs = query.order_by(CreditTransaction.id.desc()).offset((page - 1) * limit).limit(limit).all()

        tx_list = []
        for t in txs:
            tx_list.append({
                "id": t.id,
                "transaction_type": t.transaction_type,
                "amount": str(t.amount),
                "reserved_delta": str(t.reserved_delta),
                "balance_after": str(t.balance_after),
                "reserved_after": str(t.reserved_after),
                "feature_code": t.feature_code,
                "unit_price_snapshot": str(t.unit_price_snapshot) if t.unit_price_snapshot is not None else None,
                "pricing_version_snapshot": t.pricing_version_snapshot,
                "quantity": t.quantity,
                "idempotency_key": t.idempotency_key,
                "actor_user_id": t.actor_user_id,
                "job_id": t.job_id,
                "reservation_id": t.reservation_id,
                "reason": t.reason,
                "created_at": safe_dt_iso(getattr(t, 'created_at', None))
            })

        return jsonify({
            "success": True,
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit,
            "transactions": tx_list
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_CREDITS] Error fetching transactions for user {user_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to load transactions."}), 500


@admin_bp.route('/credits/pricing', methods=['GET'])
@super_admin_required
def list_feature_pricing():
    """
    Returns all feature pricing definitions (active and inactive).
    """
    from app.models.all_models import FeaturePricing

    try:
        pricings = db_session.query(FeaturePricing).order_by(FeaturePricing.feature_code.asc()).all()
        result = []
        for p in pricings:
            result.append({
                "feature_code": p.feature_code,
                "name": p.name,
                "description": p.description,
                "unit_name": p.unit_name,
                "credit_cost": str(p.credit_cost),
                "is_active": p.is_active,
                "version": p.version,
                "updated_by_user_id": p.updated_by_user_id,
                "created_at": safe_dt_iso(getattr(p, 'created_at', None)),
                "updated_at": safe_dt_iso(getattr(p, 'updated_at', None))
            })
        return jsonify({"success": True, "pricing": result}), 200
    except Exception as e:
        logger.error(f"[ADMIN_CREDITS] Error listing feature pricing: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to list feature pricing."}), 500


@admin_bp.route('/credits/pricing/<feature_code>', methods=['PATCH'])
@super_admin_required
def update_feature_pricing(feature_code: str):
    """
    Super Admin endpoint to update unit cost or active status of a feature pricing record.
    - Locks row with FOR UPDATE.
    - Validates exact decimal cost (non-negative, finite).
    - Increments version atomically if fields modified.
    - Logs audit log entry.
    """
    from decimal import Decimal, InvalidOperation
    from app.models.all_models import FeaturePricing

    admin_id = session.get('user_id')
    data = request.get_json() or {}

    try:
        # Lock pricing record with for_update
        pricing = db_session.query(FeaturePricing).filter_by(feature_code=feature_code).with_for_update().first()
        if not pricing:
            return jsonify({"success": False, "error": "NOT_FOUND", "message": f"Feature pricing '{feature_code}' not found."}), 404

        modified = False
        old_cost = getattr(pricing, 'credit_cost', None)
        old_active = getattr(pricing, 'is_active', None)
        raw_old_ver = getattr(pricing, 'version', None)
        old_version: int = int(raw_old_ver) if raw_old_ver is not None else 1

        # 1. Update credit_cost if provided
        if "credit_cost" in data:
            cost_val = data["credit_cost"]
            if cost_val is None:
                return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "credit_cost cannot be null."}), 400
            try:
                dec_cost = Decimal(str(cost_val))
            except (InvalidOperation, TypeError, ValueError):
                return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "Invalid decimal value for credit_cost."}), 400

            if not dec_cost.is_finite() or dec_cost < Decimal("0.00"):
                return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "credit_cost must be a non-negative finite number."}), 400

            dec_cost = dec_cost.quantize(Decimal("0.01"))
            if dec_cost != old_cost:
                setattr(pricing, 'credit_cost', dec_cost)
                modified = True

        # 2. Update is_active if provided
        if "is_active" in data:
            new_active = bool(data["is_active"])
            if new_active != old_active:
                setattr(pricing, 'is_active', new_active)
                modified = True

        # 3. Update description or name if provided
        curr_desc = getattr(pricing, 'description', None)
        if "description" in data and data["description"] != curr_desc:
            setattr(pricing, 'description', str(data["description"]).strip())
            modified = True

        if modified:
            setattr(pricing, 'version', old_version + 1)
            setattr(pricing, 'updated_at', datetime.utcnow())
            setattr(pricing, 'updated_by_user_id', admin_id)

            audit = AuditLog(
                admin_user_id=admin_id,
                target_user_id=None,
                action="ADMIN_UPDATE_PRICING",
                metadata_json={
                    "feature_code": feature_code,
                    "old_version": old_version,
                    "new_version": getattr(pricing, 'version', old_version + 1),
                    "old_cost": str(old_cost),
                    "new_cost": str(getattr(pricing, 'credit_cost', None)),
                    "old_active": old_active,
                    "new_active": getattr(pricing, 'is_active', None)
                }
            )
            db_session.add(audit)
            db_session.commit()

        return jsonify({
            "success": True,
            "message": "Pricing updated successfully." if modified else "No changes detected.",
            "pricing": {
                "feature_code": pricing.feature_code,
                "name": pricing.name,
                "description": pricing.description,
                "unit_name": pricing.unit_name,
                "credit_cost": str(pricing.credit_cost),
                "is_active": pricing.is_active,
                "version": pricing.version,
                "updated_at": safe_dt_iso(getattr(pricing, 'updated_at', None)),
                "updated_by_user_id": pricing.updated_by_user_id
            }
        }), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"[ADMIN_CREDITS] Error updating pricing for '{feature_code}': {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to update pricing."}), 500



# ====================================================================
# AI PROVIDER COST & USAGE DASHBOARD (TICKET 3F)
# ====================================================================

def _parse_date_bounds(start_str: str | None, end_str: str | None, default_days: int = 7) -> tuple[datetime, datetime]:
    """
    Parses and validates ISO-8601 date strings for UTC range queries.
    Defaults to the last `default_days` days up to current UTC time.
    """
    now = datetime.utcnow()
    start_dt = None
    end_dt = None

    if start_str:
        try:
            start_str_clean = start_str.strip()
            if start_str_clean.endswith('Z'):
                start_str_clean = start_str_clean[:-1]
            start_dt = datetime.fromisoformat(start_str_clean)
        except Exception:
            pass

    if end_str:
        try:
            end_str_clean = end_str.strip()
            if end_str_clean.endswith('Z'):
                end_str_clean = end_str_clean[:-1]
            end_dt = datetime.fromisoformat(end_str_clean)
        except Exception:
            pass

    if start_dt is None and end_dt is None:
        start_dt = now - timedelta(days=default_days)
        end_dt = now
    elif start_dt is not None and end_dt is None:
        end_dt = now
    elif start_dt is None and end_dt is not None:
        start_dt = end_dt - timedelta(days=default_days)
    elif start_dt is None or end_dt is None:
        start_dt = now - timedelta(days=default_days)
        end_dt = now

    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    return start_dt, end_dt


@admin_bp.route('/ai-usage/overview', methods=['GET'])
@super_admin_required
def get_ai_usage_overview():
    """
    Returns aggregated metrics and breakdowns for AI provider usage within a date range.
    Separates known costs from unknown costs and missing token counts.
    """
    try:
        start_dt, end_dt = _parse_date_bounds(
            request.args.get('start_date'),
            request.args.get('end_date'),
            default_days=7
        )

        base_filter = and_(
            AIProviderUsageLog.created_at >= start_dt,
            AIProviderUsageLog.created_at <= end_dt
        )

        # 1. Total Attempts & Status Counts
        total_attempts = db_session.query(func.count(AIProviderUsageLog.id)).filter(base_filter).scalar() or 0
        successful_attempts = db_session.query(func.count(AIProviderUsageLog.id)).filter(
            base_filter,
            AIProviderUsageLog.status == 'SUCCESS'
        ).scalar() or 0
        failed_attempts = db_session.query(func.count(AIProviderUsageLog.id)).filter(
            base_filter,
            AIProviderUsageLog.status != 'SUCCESS'
        ).scalar() or 0

        success_rate = round((successful_attempts / total_attempts * 100), 2) if total_attempts > 0 else 0.0

        # 2. Token Aggregation & Missing Metadata Count
        token_stats = db_session.query(
            func.coalesce(func.sum(AIProviderUsageLog.prompt_tokens), 0),
            func.coalesce(func.sum(AIProviderUsageLog.completion_tokens), 0),
            func.coalesce(func.sum(AIProviderUsageLog.total_tokens), 0)
        ).filter(base_filter).first()

        total_prompt_tokens = int(token_stats[0]) if token_stats else 0
        total_completion_tokens = int(token_stats[1]) if token_stats else 0
        total_tokens = int(token_stats[2]) if token_stats else 0

        missing_tokens_count = db_session.query(func.count(AIProviderUsageLog.id)).filter(
            base_filter,
            AIProviderUsageLog.total_tokens.is_(None)
        ).scalar() or 0

        # 3. Known vs Unknown Cost Aggregation
        total_known_cost = db_session.query(
            func.coalesce(func.sum(AIProviderUsageLog.estimated_cost_usd), Decimal('0.000000'))
        ).filter(
            base_filter,
            AIProviderUsageLog.estimated_cost_usd.isnot(None)
        ).scalar() or Decimal('0.000000')

        unknown_cost_count = db_session.query(func.count(AIProviderUsageLog.id)).filter(
            base_filter,
            AIProviderUsageLog.estimated_cost_usd.is_(None)
        ).scalar() or 0

        # 4. Latency / Duration Metrics
        duration_stats = db_session.query(
            func.avg(AIProviderUsageLog.duration_ms)
        ).filter(
            base_filter,
            AIProviderUsageLog.duration_ms.isnot(None)
        ).scalar()
        avg_duration_ms = round(float(duration_stats), 1) if duration_stats is not None else 0.0

        # Median duration (PostgreSQL percentile_cont if available, else fallback)
        try:
            median_val = db_session.query(
                func.percentile_cont(0.5).within_group(AIProviderUsageLog.duration_ms.asc())
            ).filter(
                base_filter,
                AIProviderUsageLog.duration_ms.isnot(None)
            ).scalar()
            median_duration_ms = round(float(median_val), 1) if median_val is not None else avg_duration_ms
        except Exception:
            median_duration_ms = avg_duration_ms

        # 5. Breakdowns by Provider, Model, and Operation
        # Breakdown by Model
        model_rows = db_session.query(
            AIProviderUsageLog.model_name,
            func.count(AIProviderUsageLog.id).label('attempts'),
            func.coalesce(func.sum(AIProviderUsageLog.prompt_tokens), 0).label('prompt_tokens'),
            func.coalesce(func.sum(AIProviderUsageLog.completion_tokens), 0).label('completion_tokens'),
            func.coalesce(func.sum(AIProviderUsageLog.total_tokens), 0).label('total_tokens'),
            func.coalesce(func.sum(AIProviderUsageLog.estimated_cost_usd), Decimal('0.000000')).label('cost_usd'),
            func.count(func.nullif(AIProviderUsageLog.estimated_cost_usd.isnot(None), True)).label('unknown_costs')
        ).filter(base_filter).group_by(AIProviderUsageLog.model_name).order_by(desc('attempts')).all()

        by_model = []
        for r in model_rows:
            by_model.append({
                "model_name": r.model_name,
                "attempts": int(r.attempts),
                "prompt_tokens": int(r.prompt_tokens),
                "completion_tokens": int(r.completion_tokens),
                "total_tokens": int(r.total_tokens),
                "estimated_cost_usd": str(r.cost_usd),
                "unknown_cost_count": int(r.unknown_costs)
            })

        # Breakdown by Operation
        op_rows = db_session.query(
            AIProviderUsageLog.operation,
            func.count(AIProviderUsageLog.id).label('attempts'),
            func.coalesce(func.sum(AIProviderUsageLog.estimated_cost_usd), Decimal('0.000000')).label('cost_usd'),
            func.sum(case((AIProviderUsageLog.status == 'SUCCESS', 1), else_=0)).label('successes'),
            func.sum(case((AIProviderUsageLog.status != 'SUCCESS', 1), else_=0)).label('failures')
        ).filter(base_filter).group_by(AIProviderUsageLog.operation).order_by(desc('attempts')).all()

        by_operation = []
        for r in op_rows:
            by_operation.append({
                "operation": r.operation,
                "attempts": int(r.attempts),
                "estimated_cost_usd": str(r.cost_usd),
                "successful_attempts": int(r.successes or 0),
                "failed_attempts": int(r.failures or 0)
            })

        # Breakdown by Provider
        provider_rows = db_session.query(
            AIProviderUsageLog.provider,
            func.count(AIProviderUsageLog.id).label('attempts'),
            func.coalesce(func.sum(AIProviderUsageLog.estimated_cost_usd), Decimal('0.000000')).label('cost_usd')
        ).filter(base_filter).group_by(AIProviderUsageLog.provider).order_by(desc('attempts')).all()

        by_provider = []
        for r in provider_rows:
            by_provider.append({
                "provider": r.provider,
                "attempts": int(r.attempts),
                "estimated_cost_usd": str(r.cost_usd)
            })

        # Daily Trend for Charts (Cost & Tokens over time)
        date_trunc_col = func.date_trunc('day', AIProviderUsageLog.created_at)
        daily_rows = db_session.query(
            date_trunc_col.label('day'),
            func.count(AIProviderUsageLog.id).label('attempts'),
            func.coalesce(func.sum(AIProviderUsageLog.prompt_tokens), 0).label('prompt_tokens'),
            func.coalesce(func.sum(AIProviderUsageLog.completion_tokens), 0).label('completion_tokens'),
            func.coalesce(func.sum(AIProviderUsageLog.total_tokens), 0).label('total_tokens'),
            func.coalesce(func.sum(AIProviderUsageLog.estimated_cost_usd), Decimal('0.000000')).label('cost_usd'),
            func.count(func.nullif(AIProviderUsageLog.estimated_cost_usd.isnot(None), True)).label('unknown_costs'),
            func.sum(case((AIProviderUsageLog.status != 'SUCCESS', 1), else_=0)).label('failed_attempts')
        ).filter(base_filter).group_by(date_trunc_col).order_by(date_trunc_col.asc()).all()

        daily_trends = []
        for r in daily_rows:
            day_str = r.day.strftime('%Y-%m-%d') if hasattr(r.day, 'strftime') else str(r.day)[:10]
            daily_trends.append({
                "date": day_str,
                "attempts": int(r.attempts),
                "prompt_tokens": int(r.prompt_tokens),
                "completion_tokens": int(r.completion_tokens),
                "total_tokens": int(r.total_tokens),
                "estimated_cost_usd": str(r.cost_usd),
                "unknown_cost_count": int(r.unknown_costs),
                "failed_attempts": int(r.failed_attempts or 0)
            })

        return jsonify({
            "success": True,
            "date_range": {
                "start": start_dt.isoformat() + "Z",
                "end": end_dt.isoformat() + "Z",
                "timezone": "UTC"
            },
            "currency": "USD",
            "summary": {
                "total_attempts": total_attempts,
                "successful_attempts": successful_attempts,
                "failed_attempts": failed_attempts,
                "success_rate": success_rate,
                "tokens": {
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_completion_tokens,
                    "total_tokens": total_tokens,
                    "missing_metadata_count": missing_tokens_count
                },
                "costs": {
                    "total_estimated_usd": str(total_known_cost),
                    "unknown_cost_count": unknown_cost_count,
                    "is_estimate": True,
                    "note": "Estimated provider cost in USD based on verified standard rates. Excludes account discounts or custom enterprise tiers."
                },
                "latency": {
                    "avg_duration_ms": avg_duration_ms,
                    "median_duration_ms": median_duration_ms
                }
            },
            "breakdowns": {
                "by_model": by_model,
                "by_operation": by_operation,
                "by_provider": by_provider,
                "daily_trends": daily_trends
            }
        }), 200

    except Exception as e:
        logger.error(f"[ADMIN_AI_USAGE] Error generating AI usage overview: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to load AI usage overview."}), 500


@admin_bp.route('/ai-usage/records', methods=['GET'])
@super_admin_required
def get_ai_usage_records():
    """
    Returns paginated, filtered individual AI provider usage records.
    Deterministic ordering: created_at DESC, id DESC.
    Never exposes prompts, completions, API keys, or raw secrets.
    """
    try:
        # Bounded pagination
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 25))))

        # Date range filter
        start_dt, end_dt = _parse_date_bounds(
            request.args.get('start_date'),
            request.args.get('end_date'),
            default_days=7
        )

        filters = [
            AIProviderUsageLog.created_at >= start_dt,
            AIProviderUsageLog.created_at <= end_dt
        ]

        # Validated query filters
        provider = (request.args.get('provider') or '').strip()
        if provider:
            filters.append(AIProviderUsageLog.provider == provider[:32])

        model_name = (request.args.get('model') or '').strip()
        if model_name:
            filters.append(AIProviderUsageLog.model_name == model_name[:64])

        operation = (request.args.get('operation') or '').strip()
        if operation:
            filters.append(AIProviderUsageLog.operation == operation[:64])

        status = (request.args.get('status') or '').strip().upper()
        if status:
            filters.append(AIProviderUsageLog.status == status[:32])

        user_id_raw = request.args.get('user_id')
        if user_id_raw:
            try:
                filters.append(AIProviderUsageLog.user_id == int(user_id_raw))
            except ValueError:
                pass

        job_id_raw = request.args.get('job_id')
        if job_id_raw:
            try:
                filters.append(AIProviderUsageLog.job_id == int(job_id_raw))
            except ValueError:
                pass

        correlation_id = (request.args.get('correlation_id') or '').strip()
        if correlation_id:
            filters.append(AIProviderUsageLog.correlation_id == correlation_id[:64])

        # Query total count for pagination
        total_count = db_session.query(func.count(AIProviderUsageLog.id)).filter(*filters).scalar() or 0
        total_pages = max(1, (total_count + limit - 1) // limit)

        # Query rows with deterministic sort
        offset = (page - 1) * limit
        rows = db_session.query(AIProviderUsageLog).filter(*filters).order_by(
            AIProviderUsageLog.created_at.desc(),
            AIProviderUsageLog.id.desc()
        ).offset(offset).limit(limit).all()

        records = []
        for log in rows:
            records.append({
                "id": log.id,
                "created_at": safe_dt_iso(getattr(log, 'created_at', None), suffix="Z"),
                "provider": log.provider,
                "model_name": log.model_name,
                "operation": log.operation,
                "status": log.status,
                "user_id": log.user_id,
                "job_id": log.job_id,
                "correlation_id": log.correlation_id,
                "prompt_tokens": log.prompt_tokens,
                "completion_tokens": log.completion_tokens,
                "total_tokens": log.total_tokens,
                "duration_ms": log.duration_ms,
                "estimated_cost_usd": str(log.estimated_cost_usd) if log.estimated_cost_usd is not None else None,
                "currency": log.provider_currency or "USD",
                "error_category": log.error_category
            })

        return jsonify({
            "success": True,
            "records": records,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }), 200

    except Exception as e:
        logger.error(f"[ADMIN_AI_USAGE] Error loading usage records: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to load usage records."}), 500


@admin_bp.route('/ai-usage/filters', methods=['GET'])
@super_admin_required
def get_ai_usage_filters():
    """
    Returns available distinct filter values (providers, models, operations, statuses)
    derived from persisted telemetry with safe fallbacks if table is empty.
    """
    try:
        providers = [
            r[0] for r in db_session.query(AIProviderUsageLog.provider).distinct().order_by(AIProviderUsageLog.provider).all() if r[0]
        ]
        models = [
            r[0] for r in db_session.query(AIProviderUsageLog.model_name).distinct().order_by(AIProviderUsageLog.model_name).all() if r[0]
        ]
        operations = [
            r[0] for r in db_session.query(AIProviderUsageLog.operation).distinct().order_by(AIProviderUsageLog.operation).all() if r[0]
        ]
        statuses = [
            r[0] for r in db_session.query(AIProviderUsageLog.status).distinct().order_by(AIProviderUsageLog.status).all() if r[0]
        ]

        # Safe defaults if table has no records yet
        if not providers:
            providers = ["GEMINI", "CLAUDE"]
        if not models:
            from app.services.gtm_pipeline_service import GEMINI_MODELS_FALLBACK
            from app.services.claude_service import CLAUDE_KNOWN_MODELS
            models = list(GEMINI_MODELS_FALLBACK) + list(CLAUDE_KNOWN_MODELS)
        if not operations:
            operations = ["SEARCH_PLANNING", "CANDIDATE_QUALIFICATION"]
        if not statuses:
            statuses = ["SUCCESS", "FAILED"]

        return jsonify({
            "success": True,
            "providers": sorted(list(set(providers))),
            "models": sorted(list(set(models))),
            "operations": sorted(list(set(operations))),
            "statuses": sorted(list(set(statuses)))
        }), 200

    except Exception as e:
        logger.error(f"[ADMIN_AI_USAGE] Error retrieving filter options: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to load filter options."}), 500


@admin_bp.route('/gtm/reconcile', methods=['POST'])
@super_admin_required
def admin_reconcile_gtm_jobs():
    """
    Super Admin endpoint to trigger manual or scheduled reconciliation of stale GTM jobs.
    Protected with row-level database locking (FOR UPDATE SKIP LOCKED).
    """
    try:
        from app.services.gtm_pipeline_service import reconcile_stale_research_jobs
        data = request.get_json(silent=True) or {}
        stale_minutes = int(data.get("max_stale_minutes", 15))
        stats = reconcile_stale_research_jobs(max_stale_minutes=stale_minutes)
        return jsonify({
            "success": True,
            "stats": stats
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_GTM_RECONCILE] Error reconciling stale research jobs: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": str(e)}), 500


# ==============================================================================
# Claude API Configuration & Connection Testing (Super Admin)
# ==============================================================================

@admin_bp.route('/claude/config', methods=['GET'])
@super_admin_required
def get_claude_settings():
    """
    Returns current Claude API configuration status and health without leaking secrets.
    """
    try:
        from app.services.claude_service import get_claude_config
        config = get_claude_config()
        return jsonify({
            "success": True,
            "config": config
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_CLAUDE] Error retrieving Claude config: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to load Claude configuration."}), 500


@admin_bp.route('/claude/config', methods=['POST'])
@super_admin_required
def update_claude_settings():
    """
    Updates Claude API configuration (API key, model, timeout).
    Never logs or exposes the API key.
    Records an AuditLog entry.
    """
    admin_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    
    api_key = data.get("api_key")
    model = data.get("model")
    timeout = data.get("timeout_seconds")

    if timeout is not None:
        try:
            timeout = int(timeout)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "timeout_seconds must be an integer."}), 400

    try:
        from app.services.claude_service import set_claude_api_config
        success, err_msg, updated_config = set_claude_api_config(
            api_key=api_key,
            model=model,
            timeout=timeout,
            admin_user_id=admin_id
        )
        if not success:
            return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": err_msg}), 400

        # Persist audit record (strictly non-secret metadata)
        audit = AuditLog(
            admin_user_id=admin_id,
            target_user_id=None,
            action="ADMIN_UPDATE_CLAUDE_CONFIG",
            metadata_json={
                "has_key": bool(api_key),
                "model": updated_config.get("model"),
                "timeout_seconds": updated_config.get("timeout_seconds")
            }
        )
        db_session.add(audit)
        db_session.commit()

        return jsonify({
            "success": True,
            "message": "Claude API configuration updated successfully.",
            "config": updated_config
        }), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"[ADMIN_CLAUDE] Error updating Claude configuration: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to save Claude configuration."}), 500


@admin_bp.route('/claude/test-connection', methods=['POST'])
@super_admin_required
def test_claude_api_connection():
    """
    Performs a minimal diagnostic ping against Claude API.
    Distinguishes:
    - 200 OK: Valid key, positive balance
    - Zero Balance / Insufficient Credits
    - Authentication failure (invalid key)
    - Rate limits, invalid model, network errors
    Never exposes secrets in logs or API response.
    Records an AuditLog entry with the diagnostic outcome.
    """
    admin_id = session.get('user_id')
    data = request.get_json(silent=True) or {}

    api_key = data.get("api_key")
    model = data.get("model")
    timeout = data.get("timeout_seconds")

    try:
        from app.services.claude_service import test_claude_connection
        result = test_claude_connection(
            api_key=api_key,
            model=model,
            timeout=timeout
        )

        # Record test in audit logs
        audit = AuditLog(
            admin_user_id=admin_id,
            target_user_id=None,
            action="ADMIN_TEST_CLAUDE_CONNECTION",
            metadata_json={
                "status": result.get("status"),
                "model_used": result.get("model_used"),
                "latency_ms": result.get("latency_ms"),
                "error_category": result.get("error_category"),
                "request_id": result.get("request_id"),
                "success": result.get("success")
            }
        )
        db_session.add(audit)
        db_session.commit()

        return jsonify({
            "success": True,
            "diagnostic": result
        }), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"[ADMIN_CLAUDE] Error testing Claude connection: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to complete connection diagnostic."}), 500


@admin_bp.route('/claude/models', methods=['GET'])
@super_admin_required
def get_claude_available_models():
    """
    Super Admin endpoint to query Anthropic's GET /v1/models endpoint using
    the configured API key. Dynamically returns the actual model catalog
    available to this account.
    """
    try:
        from app.services.claude_service import fetch_available_claude_models
        data = fetch_available_claude_models()
        return jsonify({
            "success": True,
            "result": data
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_CLAUDE] Error fetching available models: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to query Anthropic models API."}), 500






# ====================================================================
# GEMINI API CONFIGURATION & CONNECTION DIAGNOSTICS (SUPERADMIN ONLY)
# ====================================================================

@admin_bp.route('/gemini/config', methods=['GET'])
@super_admin_required
def get_gemini_settings():
    """
    Returns current Gemini API configuration status and health without leaking secrets.
    """
    try:
        from app.services.gemini_service import get_gemini_config
        config = get_gemini_config()
        return jsonify({
            "success": True,
            "config": config
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_GEMINI] Error retrieving Gemini config: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Failed to load Gemini configuration."}), 500


@admin_bp.route('/gemini/config', methods=['POST'])
@super_admin_required
def update_gemini_settings():
    """
    Updates Gemini API configuration (API key, model, timeout).
    Never logs or exposes the API key.
    Records an AuditLog entry.
    """
    admin_id = session.get('user_id')
    data = request.get_json(silent=True) or {}

    api_key = data.get('api_key')
    model = data.get('model')
    timeout = data.get('timeout')

    if timeout is not None:
        try:
            timeout = int(timeout)
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "INVALID_TIMEOUT", "message": "Timeout must be an integer."}), 400

    try:
        from app.services.gemini_service import set_gemini_api_config
        success, err_msg, updated_config = set_gemini_api_config(
            api_key=api_key,
            model=model,
            timeout=timeout,
            admin_user_id=admin_id
        )

        if not success:
            return jsonify({"success": False, "error": "CONFIG_UPDATE_FAILED", "message": err_msg or "Failed to update Gemini settings."}), 400

        # Safe audit logging (strictly NO API keys in audit logs)
        try:
            audit = AuditLog(
                admin_user_id=admin_id,
                target_user_id=None,
                action="ADMIN_UPDATE_GEMINI_CONFIG",
                metadata_json={
                    "has_key": bool(api_key),
                    "model": updated_config.get("model"),
                    "timeout_seconds": updated_config.get("timeout_seconds")
                }
            )
            db_session.add(audit)
            db_session.commit()
        except Exception as e_audit:
            logger.warning(f"[ADMIN_GEMINI] Non-critical error recording audit log for config update: {e_audit}")
            db_session.rollback()

        return jsonify({
            "success": True,
            "message": "Gemini API configuration updated successfully.",
            "config": updated_config
        }), 200

    except Exception as e:
        logger.error(f"[ADMIN_GEMINI] Error updating Gemini configuration: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to save Gemini configuration."}), 500


@admin_bp.route('/gemini/test-connection', methods=['POST'])
@super_admin_required
def test_gemini_api_connection():
    """
    Performs a minimal live diagnostic ping against Gemini API.
    Distinguishes:
    - LIVE_CONNECTION_SUCCESS
    - INSUFFICIENT_CREDITS / QUOTA_EXCEEDED
    - AUTHENTICATION_FAILED
    - MODEL_ACCESS_DENIED
    - INVALID_MODEL
    - RATE_LIMITED
    Never exposes secrets in logs or API response.
    """
    admin_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    api_key = data.get('api_key')
    model = data.get('model')

    try:
        from app.services.gemini_service import test_gemini_connection
        result = test_gemini_connection(
            api_key=api_key,
            model=model
        )

        # Safe audit logging (strictly NO API keys in audit logs)
        try:
            audit = AuditLog(
                admin_user_id=admin_id,
                target_user_id=None,
                action="ADMIN_TEST_GEMINI_CONNECTION",
                metadata_json={
                    "status": result.get("status"),
                    "model_used": result.get("model_used"),
                    "latency_ms": result.get("latency_ms"),
                    "error_category": result.get("error_category"),
                    "success": result.get("success")
                }
            )
            db_session.add(audit)
            db_session.commit()
        except Exception as e_audit:
            logger.warning(f"[ADMIN_GEMINI] Non-critical error recording audit log for connection test: {e_audit}")
            db_session.rollback()

        return jsonify({
            "success": True,
            "diagnostic": result
        }), 200

    except Exception as e:
        logger.error(f"[ADMIN_GEMINI] Error testing Gemini connection: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to complete connection diagnostic."}), 500


@admin_bp.route('/gemini/models', methods=['GET'])
@super_admin_required
def get_gemini_available_models():
    """
    Super Admin endpoint to query Google GenAI's client.models.list() using
    the configured API key. Dynamically returns the actual model catalog
    available to this account.
    """
    try:
        from app.services.gemini_service import fetch_available_gemini_models
        data = fetch_available_gemini_models()
        return jsonify({
            "success": True,
            "result": data
        }), 200
    except Exception as e:
        logger.error(f"[ADMIN_GEMINI] Error fetching available models: {e}", exc_info=True)
        return jsonify({"success": False, "error": "INTERNAL_ERROR", "message": "Failed to query Google GenAI models API."}), 500
