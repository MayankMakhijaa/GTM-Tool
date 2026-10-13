import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from app.database import db_session
import os
from cryptography.fernet import Fernet
from datetime import datetime
from app.models.all_models import UsersCompanyDetails, UsersICP, UserTable, Tone, UsersLinkedinDetails, ConnectionStatus

def normalize_website_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    try:
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path}"
        if normalized.endswith('/'):
            normalized = normalized[:-1]
        return normalized
    except Exception:
        return url

def validate_company_data(data: Dict[str, Any], is_draft: bool = False) -> Dict[str, Any]:
    url = data.get('website_url', '').strip() if data.get('website_url') else ''
    is_draft_flag = is_draft or bool(data.get('is_draft', False))
    if not is_draft_flag and not url:
        raise ValueError("website_url is required")

    ps_raw = data.get("products_services")
    if isinstance(ps_raw, list):
        products_services_val = ", ".join(str(item).strip() for item in ps_raw if item)
    elif isinstance(ps_raw, str):
        products_services_val = ps_raw.strip()
    else:
        products_services_val = ""

    return {
        "website_url": normalize_website_url(url) if url else "",
        "company_name": str(data.get("company_name") or "").strip(),
        "description": str(data.get("description") or "").strip(),
        "what_company_sells": str(data.get("what_company_sells") or "").strip(),
        "products_services": products_services_val,
        "industry": str(data.get("industry") or "").strip(),
        "company_size": str(data.get("company_size") or "").strip(),
        "revenue": str(data.get("revenue") or "").strip(),
        "location": str(data.get("location") or "").strip(),
        "rating": str(data.get("rating") or "").strip(),
        "other_details": str(data.get("other_details") or "").strip()
    }

def get_company(user_id: int) -> Optional[Dict[str, Any]]:
    company = db_session.query(UsersCompanyDetails).filter_by(user_id=user_id).first()
    if not company:
        return None
    return {
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
        "other_details": company.other_details,
        "scrape_status": company.scrape_status,
        "edited_fields": company.edited_fields or []
    }

def save_company(user_id: int, data: Dict[str, Any], is_draft: bool = False) -> Dict[str, Any]:
    is_draft_flag = is_draft or bool(data.get("is_draft", False))
    valid_data = validate_company_data(data, is_draft=is_draft_flag)

    company = db_session.query(UsersCompanyDetails).filter_by(user_id=user_id).first()
    is_new = False
    if not company:
        company = UsersCompanyDetails(user_id=user_id, scrape_status="MANUAL")
        db_session.add(company)
        is_new = True

    # Track edited fields if updating
    edited = set(company.edited_fields or [])
    for key, value in valid_data.items():
        if not is_new and getattr(company, key) != value:
            edited.add(key)
        setattr(company, key, value)

    if not is_new:
        company.edited_fields = list(edited)

    # Advance onboarding state if not draft and required fields are set
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if user and user.onboarding_step in ["LINKEDIN", "COMPANY"] and not is_draft_flag and valid_data.get("website_url"):
        user.onboarding_step = "ICP"

    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise e

    return get_company(user_id)


def validate_icp_data(data: Dict[str, Any]) -> Dict[str, Any]:
    tone_str = data.get("tone", "FORMAL").strip().upper()
    try:
        tone = Tone(tone_str).value
    except ValueError:
        tone = Tone.FORMAL.value

    return {
        "target_customer": data.get("target_customer", "").strip(),
        "company_size": data.get("company_size", "").strip(),
        "revenue_range": data.get("revenue_range", "").strip(),
        "industry": data.get("industry", "").strip(),
        "location": data.get("location", "").strip(),
        "tone": tone,
        "target_jobs_roles": data.get("target_jobs_roles", ""),
        "keywords": data.get("keywords", ""),
        "exclusions": data.get("exclusions", ""),
        "signals": data.get("signals") if isinstance(data.get("signals"), (list, dict)) else None
    }

def get_icp(user_id: int) -> Optional[Dict[str, Any]]:
    icp = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    if not icp:
        return None
    return {
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
        "summary_report": icp.summary_report
    }

def save_icp(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    valid_data = validate_icp_data(data)

    icp = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    is_new = False
    if not icp:
        icp = UsersICP(user_id=user_id, version=1)
        db_session.add(icp)
        is_new = True

    qualification_fields = [
        'target_customer', 'company_size', 'revenue_range',
        'target_jobs_roles', 'industry', 'location',
        'keywords', 'exclusions', 'signals'
    ]

    requires_version_bump = False

    for key, value in valid_data.items():
        if not is_new and key in qualification_fields:
            if getattr(icp, key) != value:
                requires_version_bump = True
        setattr(icp, key, value)

    if requires_version_bump:
        icp.version += 1

    # Advance onboarding state to DONE upon ICP setup completion
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if user and user.onboarding_step in ("LINKEDIN", "COMPANY", "ICP"):
        user.onboarding_step = "DONE"

    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise e

    return get_icp(user_id)

from app.integrations.linkedin.voyager_client import encrypt_credential, decrypt_credential

def get_linkedin_connection_status(user_id: int) -> Dict[str, Any]:
    linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    return {
        "connected": linkedin is not None and linkedin.connection_status == ConnectionStatus.CONNECTED.value,
        "status": linkedin.connection_status if linkedin else ConnectionStatus.DISCONNECTED.value
    }

def save_linkedin_connection(user_id: int, session_cookie: str) -> Dict[str, Any]:
    if not session_cookie:
        raise ValueError("Session credential is required")

    linkedin = db_session.query(UsersLinkedinDetails).filter_by(user_id=user_id).first()
    if not linkedin:
        linkedin = UsersLinkedinDetails(user_id=user_id)
        db_session.add(linkedin)

    linkedin.auth_data_encrypted = encrypt_credential(session_cookie)
    linkedin.connection_status = ConnectionStatus.CONNECTED.value
    linkedin.consent_at = datetime.utcnow()

    # Advance onboarding state to COMPANY if at LINKEDIN
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    if user and user.onboarding_step == "LINKEDIN":
        user.onboarding_step = "COMPANY"

    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise e

    return get_linkedin_connection_status(user_id)

def get_onboarding_status(user_id: int) -> Dict[str, Any]:
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    company = db_session.query(UsersCompanyDetails).filter_by(user_id=user_id).first()
    icp = db_session.query(UsersICP).filter_by(user_id=user_id).first()

    return {
        "success": True,
        "onboarding_step": user.onboarding_step if user else "LINKEDIN",
        "company_completed": company is not None,
        "icp_completed": icp is not None,
        "optimization_status": user.optimization_status if user else "NOT_OFFERED"
    }

def get_optimization_settings(user_id: int) -> Dict[str, Any]:
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    icp = db_session.query(UsersICP).filter_by(user_id=user_id).first()

    summary = (icp.summary_report or {}) if icp and icp.summary_report else {}
    applied_suggestions = summary.get("applied_suggestions", [])
    settings = summary.get("settings", {
        "priority_filter": "all",
        "skill_ordering": ["Pipeline Velocity", "RevOps Architecture", "Outbound Intelligence"],
        "auto_save": True
    })

    return {
        "success": True,
        "optimization_status": user.optimization_status if user else "NOT_OFFERED",
        "onboarding_step": user.onboarding_step if user else "OPTIMIZATION",
        "applied_suggestions": applied_suggestions,
        "settings": settings
    }

def save_optimization_settings(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    user = db_session.query(UserTable).filter_by(user_id=user_id).first()
    icp = db_session.query(UsersICP).filter_by(user_id=user_id).first()
    if not icp:
        icp = UsersICP(user_id=user_id, version=1)
        db_session.add(icp)

    summary = dict(icp.summary_report or {}) if icp.summary_report else {}

    if "optimization_status" in data:
        status_val = str(data["optimization_status"]).upper()
        if user:
            user.optimization_status = status_val

    if data.get("mark_completed") or data.get("optimization_status") in ["COMPLETED", "ACCEPTED"]:
        if user:
            user.onboarding_step = "DONE"

    if "applied_suggestion" in data:
        applied = list(summary.get("applied_suggestions", []))
        item = data["applied_suggestion"]
        if item not in applied:
            applied.append(item)
        summary["applied_suggestions"] = applied

    if "settings" in data:
        curr_settings = dict(summary.get("settings", {}))
        curr_settings.update(data["settings"])
        summary["settings"] = curr_settings

    icp.summary_report = summary

    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise e

    return get_optimization_settings(user_id)

