import os
import shutil
import sys

# Append current directory to path so we can import from app
sys.path.append(os.getcwd())

from app.database import db_session
from sqlalchemy import text

TABLES_TO_CLEAR = [
    'connect_and_message',
    'users_profiles',
    'research_jobs',
    'users_linkedin_details',
    'users_icp',
    'users_company_details',
    'global_profiles',
    'user_table'
]

def get_row_count(table_name):
    try:
        result = db_session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar()
    except Exception as e:
        print(f"Error getting count for {table_name}: {e}")
        return 0

def clear_directory(dir_path):
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            print(f"Removed directory tree: {dir_path}")
        except Exception as e:
            print(f"Error removing {dir_path}: {e}")
    os.makedirs(dir_path, exist_ok=True)
    print(f"Ensured directory exists and is empty: {dir_path}")

def main():
    print("--- PRE-RESET COUNTS ---")
    for table in TABLES_TO_CLEAR:
        count = get_row_count(table)
        print(f"{table}: {count} rows")

    print("\n--- PERFORMING RESET ---")
    try:
        for table in TABLES_TO_CLEAR:
            db_session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        db_session.commit()
        print("Database tables truncated successfully.")
    except Exception as e:
        db_session.rollback()
        print(f"Error truncating tables: {e}")

    profile_dir = os.path.join(os.getcwd(), 'browser_profile')
    output_dir = os.path.join(os.getcwd(), 'output')
    
    clear_directory(profile_dir)
    clear_directory(output_dir)

    print("\n--- POST-RESET VERIFICATION ---")
    for table in TABLES_TO_CLEAR:
        count = get_row_count(table)
        print(f"{table}: {count} rows")
        
    print(f"browser_profile/ is empty: {len(os.listdir(profile_dir)) == 0}")
    print(f"output/ is empty: {len(os.listdir(output_dir)) == 0}")

if __name__ == "__main__":
    main()
