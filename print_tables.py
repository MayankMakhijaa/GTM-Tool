import os
import sys

sys.path.append(os.path.join(os.getcwd()))
from app.database import Base, engine
import app.models.all_models

def main():
    tables = Base.metadata.sorted_tables
    for t in tables:
        print(t.name)

if __name__ == "__main__":
    main()
