import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.getcwd(), "gtm_opportunities.db")

def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def insert_lead(user_id: int, lead_data: Dict[str, Any]) -> int:
    """Inserts a generated lead into the leads table and returns the lead_id."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    score = lead_data.get("lead_score", 0)
    if not isinstance(score, (int, float)):
        try:
            score = int(score)
        except (ValueError, TypeError):
            score = 0

    created_at = datetime.now().astimezone().isoformat()
    
    cursor.execute("""
        INSERT INTO leads (
            user_id, score, first_name, last_name, full_name, 
            company, role, intent, business_need, reason, 
            lead_type, email, phone_no, linkedin_profile, 
            source, source_reference, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, (
        user_id,
        score,
        lead_data.get("first_name"),
        lead_data.get("last_name"),
        lead_data.get("name"),  # Mapped to full_name
        lead_data.get("company"),
        lead_data.get("role"),
        lead_data.get("intent"),
        lead_data.get("business_need"),
        lead_data.get("reason"),
        lead_data.get("lead_type"),
        lead_data.get("email"),
        lead_data.get("phone"),
        lead_data.get("profile_url"),
        lead_data.get("source", "linkedin_post"),
        lead_data.get("source_reference"),
        created_at
    ))
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id

def get_history_leads_db(user_id: int, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns user's leads, optionally filtered by date, newest first."""
    conn = _get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM leads WHERE user_id = ?"
    params = [user_id]
    
    if from_date:
        query += " AND created_at >= ?"
        params.append(from_date)
        
    if to_date:
        # User requested inclusive of to_date, so we append 23:59:59 to capture all entries that day
        query += " AND created_at <= ?"
        params.append(f"{to_date}T23:59:59.999999")
        
    query += " ORDER BY created_at DESC"
    
    rows = cursor.execute(query, params).fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_email_leads_db(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns only leads that have a valid, non-empty Email address for the given user,
    deduplicated gracefully by preserving the most recent matching record.
    """
    leads = get_history_leads_db(user_id)
    
    # Filter for valid emails
    email_leads = [
        l for l in leads
        if l.get("email") and isinstance(l.get("email"), str) and l.get("email", "").strip() != ""
    ]
    
    # Simple Deduplication: keep the first (newest) occurrence of an email
    seen_emails = set()
    deduped = []
    for lead in email_leads:
        email = lead["email"].strip().lower()
        if email not in seen_emails:
            seen_emails.add(email)
            deduped.append(lead)
            
    return deduped
