import sys
import os
sys.path.insert(0, os.getcwd())

import psycopg
from sqlalchemy import text
from app.database import engine

print(f"Target engine URL: {engine.url}")

# Verify that target is indeed localhost fameweb
if engine.url.database != "fameweb":
    raise RuntimeError(f"Safety abort: Expected database 'fameweb', got '{engine.url.database}'")

# Tables to clear in reverse dependency order
tables_to_clear = [
    "users_profiles",
    "connect_and_message",
    "research_jobs",
    "users_company_details",
    "users_icp",
    "users_linkedin_details",
    "global_profiles",
    "user_table"
]

with engine.begin() as conn:
    for t in tables_to_clear:
        res = conn.execute(text(f'DELETE FROM "{t}";'))
        print(f"Cleared table '{t}' (deleted rows)")

    # Reset sequences so next auto-increment ID starts at 1
    sequences = [
        "user_table_user_id_seq",
        "users_company_details_id_seq",
        "users_icp_id_seq",
        "users_linkedin_details_id_seq",
        "research_jobs_id_seq",
        "users_profiles_id_seq",
        "connect_and_message_id_seq",
        "global_profiles_global_id_seq"
    ]
    for seq in sequences:
        try:
            conn.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1;"))
            print(f"Reset sequence '{seq}' to 1")
        except Exception as e:
            print(f"Sequence {seq} note: {e}")

print("\n--- Verifying Row Counts in fameweb ---")
with engine.connect() as conn:
    for t in tables_to_clear:
        cnt = conn.execute(text(f'SELECT count(*) FROM "{t}";')).scalar()
        print(f"Table '{t}': {cnt} rows")

    alembic_cnt = conn.execute(text('SELECT count(*) FROM "alembic_version";')).scalar()
    print(f"Table 'alembic_version' (preserved): {alembic_cnt} rows")
