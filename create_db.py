"""
Database initialization script for the AI Resume Screener.
Run this script once to create the local SQLite database.
"""
import sqlite3
import logging
from config import DB_PATH

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_database():
    """
    Reads the schema.sql file and executes it against the SQLite database.
    """
    try:
        # Connect to the database (it will be created if it doesn't exist)
        with sqlite3.connect(DB_PATH) as conn:
            with open("schema.sql", "r", encoding="utf-8") as f:
                schema_script = f.read()

            # Execute the combined SQL script
            conn.executescript(schema_script)
            conn.commit()

        logger.info(f"Successfully created/updated database at: {DB_PATH}")

    except FileNotFoundError:
        logger.error("Error: 'schema.sql' file not found in the root directory.")
    except sqlite3.Error as e:
        logger.error(f"SQLite error occurred: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    create_database()