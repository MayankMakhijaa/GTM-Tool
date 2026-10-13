import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.getcwd())
import psycopg
from app.database import engine
from sqlalchemy import inspect, text

os.makedirs("backups", exist_ok=True)
backup_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
json_backup_path = os.path.abspath(f"backups/fameweb_backup_{backup_timestamp}.json")

# 1. Export all tables to JSON
insp = inspect(engine)
tables = insp.get_table_names()
backup_data = {}

with engine.connect() as conn:
    for t in tables:
        rows = conn.execute(text(f'SELECT * FROM "{t}"')).fetchall()
        cols = [c["name"] for c in insp.get_columns(t)]
        table_rows = []
        for r in rows:
            row_dict = {}
            for col_name, val in zip(cols, r):
                if isinstance(val, datetime):
                    row_dict[col_name] = val.isoformat()
                elif isinstance(val, (bytes, bytearray)):
                    row_dict[col_name] = val.hex()
                else:
                    row_dict[col_name] = val
            table_rows.append(row_dict)
        backup_data[t] = table_rows

with open(json_backup_path, "w", encoding="utf-8") as f:
    json.dump(backup_data, f, indent=2, default=str)

print(f"JSON backup written to: {json_backup_path}")
print(f"Backed up {len(tables)} tables, size: {os.path.getsize(json_backup_path)} bytes")

# 2. Also create a clone database in PostgreSQL if possible
clone_db_name = f"fameweb_backup_{backup_timestamp}"
try:
    with psycopg.connect("postgresql://postgres:root@localhost:5432/postgres", autocommit=True) as conn:
        # Terminate any connections to fameweb
        conn.execute("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'fameweb'
              AND pid <> pg_backend_pid();
        """)
        conn.execute(f'CREATE DATABASE "{clone_db_name}" WITH TEMPLATE fameweb;')
        print(f"PostgreSQL template clone created: {clone_db_name}")
except Exception as e:
    print(f"Template clone notice (JSON backup remains authoritative): {e}")

# 3. Verify backup file exists and is valid
with open(json_backup_path, "r", encoding="utf-8") as f:
    verified = json.load(f)
    for t, rows in verified.items():
        print(f"Verified {t}: {len(rows)} records")
