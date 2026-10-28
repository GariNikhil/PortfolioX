"""SQLite schema: creation, versioned upgrades, and money storage.

Amount columns are stored as INTEGER paise (1 rupee = 100 paise) so that
sums stay exact. ensure_schema() creates the version-2 tables on a fresh
database and migrates an older rupee-REAL (v1) database in place, preserving
row values by multiplying stored amounts by 100.
"""

from database.db import transaction

SCHEMA_VERSION = 2

# v2 table definitions. Money columns are INTEGER paise; quantity stays REAL
# because fractional share counts are legitimate. profit_loss has no
# non-negative check because losses are negative by design.
_TABLES = {
    "transactions": """
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        isin TEXT,
        exchange TEXT,
        transaction_type TEXT NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
        quantity REAL NOT NULL,
        price INTEGER NOT NULL DEFAULT 0 CHECK (price >= 0),
        brokerage INTEGER NOT NULL DEFAULT 0 CHECK (brokerage >= 0),
        taxes INTEGER NOT NULL DEFAULT 0 CHECK (taxes >= 0),
        net_amount INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "holdings": """
    CREATE TABLE holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        average_price INTEGER NOT NULL DEFAULT 0 CHECK (average_price >= 0),
        invested_amount INTEGER NOT NULL DEFAULT 0 CHECK (invested_amount >= 0),
        market_value INTEGER NOT NULL DEFAULT 0 CHECK (market_value >= 0),
        profit_loss INTEGER NOT NULL DEFAULT 0
    )
    """,
    "dividends": """
    CREATE TABLE dividends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        dividend_date TEXT NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0
    )
    """,
    "imports": """
    CREATE TABLE imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        import_type TEXT,
        imported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT
    )
    """,
    "symbol_aliases": """
    CREATE TABLE symbol_aliases (
        alias TEXT PRIMARY KEY,
        canonical TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
}

# Money columns multiplied by 100 during the v1 -> v2 migration, keyed by
# table. Columns not listed here are carried over unchanged.
_MIGRATION_MULTIPLIES = {
    "transactions": ("price", "brokerage", "taxes", "net_amount"),
    "holdings": ("average_price", "invested_amount", "market_value", "profit_loss"),
    "dividends": ("amount",),
}


def ensure_schema():
    """Create tables when missing and migrate a v1 database to v2.

    Fresh database: all tables are created and user_version is set to
    SCHEMA_VERSION. Existing database: each TRANSACTIONS-style table that
    still stores money as REAL is moved aside, recreated with v2 columns,
    back-filled with amounts multiplied by 100, and the old table dropped.
    A migration that hits constraint violations (bad money data) fails
    loudly instead of silently altering values.
    """

    with transaction() as connection:
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        if "transactions" not in existing:
            migration_needed = False
        else:
            migration_needed = _is_v1(connection, "transactions")

        for table, ddl in _TABLES.items():
            if table not in existing:
                connection.execute(ddl)

        if migration_needed:
            _migrate_v1_tables(connection)

        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _is_v1(connection, table):
    """Report whether a table stores money as REAL (v1) instead of paise."""

    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
    for column in columns:
        if column["name"] == "price" and column["type"].upper() == "REAL":
            return True
    return False


def _migrate_v1_tables(connection):
    """Move each v1 money table to v2, multiplying amount columns by 100."""

    for table, money_columns in _MIGRATION_MULTIPLIES.items():
        columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
        tables_with_money = [
            column["name"] for column in columns if column["name"] in money_columns
        ]
        if not tables_with_money:
            continue

        connection.execute(f"ALTER TABLE {table} RENAME TO {table}_v1")
        connection.execute(_TABLES[table])

        selects = [
            f"CAST(ROUND({column} * 100) AS INTEGER)" if column in tables_with_money
            else column
            for column in (cell["name"] for cell in columns)
        ]
        names = ", ".join(cell["name"] for cell in columns)

        connection.execute(
            f"INSERT INTO {table} ({names}) "
            f"SELECT {', '.join(selects)} FROM {table}_v1"
        )
        connection.execute(f"DROP TABLE {table}_v1")


def create_tables():
    """Backward-compatible alias for ensure_schema()."""

    ensure_schema()


if __name__ == "__main__":
    ensure_schema()
    print("Database tables created successfully")
