import sqlite3, os

db_path = r'C:\Users\Admin\AppData\Roaming\pgadmin\pgadmin4.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]
    print('Tables:', tables)
    if 'server' in tables:
        cur.execute("SELECT name, host, port, username FROM server")
        print('Servers:', cur.fetchall())
