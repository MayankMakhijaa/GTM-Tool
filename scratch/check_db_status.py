import sys
import os
sys.path.insert(0, os.getcwd())
from sqlalchemy import inspect, text
from app.database import engine

insp = inspect(engine)
tables = insp.get_table_names()
print("Existing Tables:", tables)

with engine.connect() as conn:
    for t in tables:
        cnt = conn.execute(text(f'SELECT count(*) FROM "{t}"')).scalar()
        print(f"Table {t}: {cnt} rows")
