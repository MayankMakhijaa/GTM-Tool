import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Any

def generate_excel(analyzed_comments: List[Dict[str, Any]]) -> str:
    """
    Generate an Excel file with two sheets: Qualified Leads and All Analyzed Comments.
    Returns the generated filename.
    """
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)
    
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"linkedin_leads_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)
    
    # Filter qualified leads
    qualified_leads = [c for c in analyzed_comments if isinstance(c, dict) and c.get("lead") is True]
    
    # Define exact 11 columns for Qualified Leads
    leads_keys = [
        "lead_score", "name", "company", "role", "intent",
        "business_need", "reason", "lead_type", "email", "phone", "profile_url"
    ]
    cols = [
        "Score", "Person's Name", "Company", "Role", "Intent",
        "Business Need", "Reason", "Lead Type", "Email", "Phone No.", "LinkedIn Profile"
    ]
    
    # Create DataFrames
    if qualified_leads:
        df_leads = pd.DataFrame(qualified_leads)
        for key in leads_keys:
            if key not in df_leads.columns:
                df_leads[key] = None
        df_leads = df_leads[leads_keys]  # type: ignore
        df_leads.columns = cols
    else:
        df_leads = pd.DataFrame({c: [] for c in cols})

    df_all = pd.DataFrame(analyzed_comments)
    df_meta = pd.DataFrame([
        {"Property": "Generated At", "Value": now.isoformat()},
        {"Property": "Generator Version", "Value": "1.4"}
    ])
        
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df_leads.to_excel(writer, sheet_name="Qualified Leads", index=False)
        df_all.to_excel(writer, sheet_name="All Analyzed Comments", index=False)
        df_meta.to_excel(writer, sheet_name="Run Metadata", index=False)
        
    return filename
