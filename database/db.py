import sqlite3
from pathlib import Path


# Database location
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FOLDER = PROJECT_ROOT / "data"
DB_FILE = "portfoliox.db"
DB_PATH = DB_FOLDER / DB_FILE


def create_connection():
    """
    Creates and returns a database connection.
    """

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def execute_query(query, params=()):
    """
    Execute INSERT, UPDATE, DELETE queries.
    """

    connection = create_connection()

    cursor = connection.cursor()

    cursor.execute(query, params)

    connection.commit()

    connection.close()


def fetch_all(query, params=()):
    """
    Execute SELECT queries.
    """

    connection = create_connection()

    cursor = connection.cursor()

    cursor.execute(query, params)

    result = cursor.fetchall()

    connection.close()

    return result