import sqlite3
import glob

print("DATABASES FOUND:")
dbs = glob.glob("*.db")
for db in dbs:
    print(f"\n--- Database: {db} ---")
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT name, type, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for tbl_name, tbl_type, tbl_sql in tables:
            print(f"Table: {tbl_name}")
            print(tbl_sql)
        conn.close()
    except Exception as e:
        print(f"Error reading {db}: {e}")
