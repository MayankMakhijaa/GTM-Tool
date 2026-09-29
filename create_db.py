import psycopg
from psycopg.errors import DuplicateDatabase

def create_database():
    try:
        # Connect to the default postgres database to create a new one
        conn = psycopg.connect(
            "dbname=postgres user=postgres password=root host=localhost",
            autocommit=True
        )
        with conn.cursor() as cur:
            try:
                cur.execute("CREATE DATABASE fameweb")
                print("Database 'fameweb' created successfully.")
            except DuplicateDatabase:
                print("Database 'fameweb' already exists.")
        conn.close()
    except Exception as e:
        print(f"Error connecting/creating DB: {e}")

if __name__ == "__main__":
    create_database()
