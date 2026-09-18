import sqlite3
import os

db = 'gtm_opportunities.db'
if not os.path.exists(db):
    print('DB not found')
else:
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print('Tables:', tables)
    for t in tables:
        c.execute(f'PRAGMA table_info({t})')
        cols = c.fetchall()
        print(f'\nTable: {t}')
        print('  Columns:', [col[1] for col in cols])
        c.execute(f'SELECT COUNT(*) FROM {t}')
        print('  Rows:', c.fetchone()[0])
    conn.close()
