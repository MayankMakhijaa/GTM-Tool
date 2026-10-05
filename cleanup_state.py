import os
import sys
import shutil
from sqlalchemy import text

sys.path.append(os.path.join(os.getcwd()))
from app.database import db_session

def clear_directory(dir_path):
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    os.makedirs(dir_path, exist_ok=True)
    
    # Verify it is empty
    return len(os.listdir(dir_path)) == 0

def cleanup():
    tables_to_truncate = [
        "users_profiles",
        "connect_and_message",
        "research_jobs",
        "users_company_details",
        "users_icp",
        "users_linkedin_details",
        "global_profiles",
        "user_table"
    ]
    
    # 1. Truncate Tables
    print("Executing TRUNCATE on application tables...")
    try:
        truncate_sql = f"TRUNCATE TABLE {', '.join(tables_to_truncate)} CASCADE;"
        db_session.execute(text(truncate_sql))
        db_session.commit()
        print("Truncate successful.")
    except Exception as e:
        db_session.rollback()
        print(f"Error truncating tables: {e}")
        return

    # 2. Verify Table Rows
    print("\nVerifying row counts...")
    verification_results = {}
    for table in tables_to_truncate:
        count = db_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        verification_results[table] = count
        print(f"{table}: {count} rows")

    # 3. Clear Filesystem
    print("\nClearing filesystem storage...")
    browser_profile_path = os.path.join(os.getcwd(), 'browser_profile')
    output_path = os.path.join(os.getcwd(), 'output')
    
    bp_cleared = clear_directory(browser_profile_path)
    print(f"browser_profile directory cleared and recreated. Empty: {bp_cleared}")
    
    out_cleared = clear_directory(output_path)
    print(f"output directory cleared and recreated. Empty: {out_cleared}")

if __name__ == "__main__":
    cleanup()
