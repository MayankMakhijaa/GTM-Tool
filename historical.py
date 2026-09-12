import os
import glob
import re
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd


def get_file_run_datetime(filepath: str, excel_file: pd.ExcelFile) -> datetime:
    """
    Extract generation run datetime from Excel 'Run Metadata' sheet if present,
    else fallback to filename timestamp or file modification time.
    """
    if "Run Metadata" in excel_file.sheet_names:
        try:
            df_meta = pd.read_excel(filepath, sheet_name="Run Metadata")
            if not df_meta.empty and "Property" in df_meta.columns and "Value" in df_meta.columns:
                row = df_meta[df_meta["Property"] == "Generated At"]
                if not row.empty:
                    val_str = str(row.iloc[0]["Value"]).strip()
                    dt = datetime.fromisoformat(val_str)
                    return dt.replace(tzinfo=None)
        except Exception:
            pass

    basename = os.path.basename(filepath)
    match = re.search(r"linkedin_leads_(\d{8})_(\d{6})\.xlsx", basename)
    if match:
        try:
            dt = datetime.strptime(f"{match.group(1)}_{match.group(2)}", "%Y%m%d_%H%M%S")
            return dt
        except Exception:
            pass

    try:
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime)
    except Exception:
        return datetime.now()


def format_date_label(run_dt: datetime) -> str:
    """
    Formats run datetime into human-friendly date labels:
    - Today
    - Yesterday
    - September 10, 2026
    """
    now = datetime.now()
    today_date = now.date()
    run_dt_naive = run_dt.replace(tzinfo=None)
    run_date = run_dt_naive.date()

    delta_days = (today_date - run_date).days

    if delta_days == 0:
        return "Today"
    elif delta_days == 1:
        return "Yesterday"
    else:
        day_str = run_dt_naive.strftime("%d").lstrip("0")
        month_year_str = run_dt_naive.strftime("%B") + f" {day_str}, " + run_dt_naive.strftime("%Y")
        return month_year_str


def parse_all_excel_qualified_runs() -> List[Dict[str, Any]]:
    """
    Reads ALL output/*.xlsx files.
    Groups leads by generation run, preserving run order and NOT globally deduplicating.
    Returns list of run objects sorted newest run first.
    """
    output_dir = os.path.join(os.getcwd(), "output")
    if not os.path.exists(output_dir):
        return []

    excel_files = glob.glob(os.path.join(output_dir, "*.xlsx"))
    if not excel_files:
        return []

    runs: List[Dict[str, Any]] = []

    for filepath in excel_files:
        try:
            excel_file = pd.ExcelFile(filepath)
            if "Qualified Leads" not in excel_file.sheet_names:
                continue

            df = pd.read_excel(filepath, sheet_name="Qualified Leads")
            if df.empty:
                continue

            run_dt = get_file_run_datetime(filepath, excel_file)
            date_label = format_date_label(run_dt)

            records: List[Dict[str, Any]] = df.to_dict(orient="records")  # type: ignore
            run_leads: List[Dict[str, Any]] = []

            for row in records:
                score_val = row.get("Score")
                try:
                    score = int(score_val) if (score_val is not None and not pd.isna(score_val)) else 0
                except Exception:
                    score = 0

                name_val = row.get("Person's Name")
                name = str(name_val).strip() if (name_val is not None and not pd.isna(name_val) and str(name_val).strip() != "") else "Unknown"

                company_val = row.get("Company")
                company = str(company_val).strip() if (company_val is not None and not pd.isna(company_val)) else None

                role_val = row.get("Role")
                role = str(role_val).strip() if (role_val is not None and not pd.isna(role_val)) else None

                intent_val = row.get("Intent")
                intent = str(intent_val).strip() if (intent_val is not None and not pd.isna(intent_val)) else None

                need_val = row.get("Business Need")
                business_need = str(need_val).strip() if (need_val is not None and not pd.isna(need_val)) else None

                reason_val = row.get("Reason")
                reason = str(reason_val).strip() if (reason_val is not None and not pd.isna(reason_val)) else None

                type_val = row.get("Lead Type")
                lead_type = str(type_val).strip() if (type_val is not None and not pd.isna(type_val)) else None

                email_val = row.get("Email")
                email = str(email_val).strip() if (email_val is not None and not pd.isna(email_val) and "@" in str(email_val)) else None

                phone_val = row.get("Phone No.")
                phone = str(phone_val).strip() if (phone_val is not None and not pd.isna(phone_val)) else None

                profile_val = row.get("LinkedIn Profile")
                profile_url = str(profile_val).strip() if (profile_val is not None and not pd.isna(profile_val)) else None

                lead_dict = {
                    "lead": True,
                    "lead_score": score,
                    "name": name,
                    "company": company,
                    "role": role,
                    "intent": intent,
                    "business_need": business_need,
                    "reason": reason,
                    "lead_type": lead_type,
                    "email": email,
                    "phone": phone,
                    "profile_url": profile_url,
                    "run_date_label": date_label,
                    "run_timestamp": run_dt.isoformat(),
                }
                run_leads.append(lead_dict)

            if run_leads:
                runs.append({
                    "run_datetime": run_dt,
                    "run_timestamp": run_dt.isoformat(),
                    "date_label": date_label,
                    "filepath": filepath,
                    "leads": run_leads
                })

        except Exception as e:
            print(f"Notice reading Excel file {filepath}: {e}")
            continue

    runs.sort(key=lambda x: x["run_datetime"], reverse=True)
    return runs


def get_all_historical_leads() -> List[Dict[str, Any]]:
    """
    Returns ALL historical qualified leads from all output/*.xlsx files,
    grouped by generation run (newest run first).
    No global deduplication is performed so repeated leads across separate runs are preserved.
    Within each run, the order of leads is preserved.
    """
    runs = parse_all_excel_qualified_runs()
    all_leads: List[Dict[str, Any]] = []

    for run in runs:
        for lead in run["leads"]:
            all_leads.append(lead)

    return all_leads


def get_historical_email_leads() -> List[Dict[str, Any]]:
    """
    Returns only historical qualified leads that have a valid, non-empty Email address.
    """
    all_leads = get_all_historical_leads()
    email_leads = [
        l for l in all_leads
        if l.get("email") and isinstance(l.get("email"), str) and l.get("email", "").strip() != ""
    ]
    return email_leads

