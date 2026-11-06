import sqlite3
from contextlib import contextmanager

from paths import app_root, data_dir

# Database location. Resolved from the running app rather than from this
# file, so a frozen build keeps its database next to the executable
# instead of inside a temporary bundle folder.
PROJECT_ROOT = app_root()
DB_FOLDER = data_dir()
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
