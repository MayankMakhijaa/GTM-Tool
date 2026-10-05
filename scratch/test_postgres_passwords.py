import psycopg

passwords = [
    'postgres', 'root', 'admin', 'password', '123456', 'postgres123',
    'shreyas', 'fameweb', 'kaashif', '1234', '12345', 'pass', 'Postgres',
    'Postgres123', 'Root', 'Admin', 'fameweb123', '123'
]

for db in ['postgres', 'fameweb']:
    for pwd in passwords:
        try:
            conn = psycopg.connect(
                f"host=127.0.0.1 port=5432 dbname={db} user=postgres password={pwd}",
                connect_timeout=2
            )
            print(f"SUCCESS: Connected to '{db}' as user 'postgres' with a valid password!")
            conn.close()
            break
        except Exception as e:
            pass
