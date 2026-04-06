import sqlite3
from config import DB_PATH

def create_database():

    with sqlite3.connect(DB_PATH) as conn:

        with open("schema.sql") as f:
            conn.executescript(f.read())

    print("Database created:", DB_PATH)


if __name__ == "__main__":
    create_database()