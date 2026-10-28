import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Database location
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FOLDER = PROJECT_ROOT / "data"
DB_FILE = "portfoliox.db"
DB_PATH = DB_FOLDER / DB_FILE


def create_connection():
    """
    Creates and returns a database connection.

    Rows are returned as sqlite3.Row objects so consumers can access
    columns by name (for example, row["symbol"] instead of row[2]).
    """

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def transaction():
    """
    Context manager yielding an open connection for multi-statement work.

    Commits on success, rolls back when the block raises, and always closes
    the connection. Prefer this for batch operations (for example, imports).
    """

    connection = create_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def execute_query(query, params=()):
    """
    Execute INSERT, UPDATE, DELETE queries.
    """

    with transaction() as connection:
        connection.execute(query, params)


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
