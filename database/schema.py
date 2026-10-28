"""SQLite schema: creation, versioned upgrades, and money storage.

Amount columns are stored as INTEGER paise (1 rupee = 100 paise) so that
sums stay exact. ensure_schema() creates the current tables on a fresh
database, migrates an older rupee-REAL (v1) database in place preserving
row values by multiplying stored amounts by 100, upgrades a v2 database
in place with the v3 additions (accounts, prices, account_id), and a v3
database with the v4 additions (account current_balance, manual_holdings).
"""

from database.db import transaction

SCHEMA_VERSION = 4

# Table definitions. Money columns are INTEGER paise; quantity stays REAL
# because fractional share counts are legitimate. profit_loss has no
# non-negative check because losses are negative by design. Holdings are
# per account: one row per (account, symbol) pair. account_id is nullable
# so pre-v3 transactions/holdings stay valid as "Unassigned".
_TABLES = {
    "accounts": """
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK (kind IN ('BROKER', 'PERSONAL')),
        is_main INTEGER NOT NULL DEFAULT 0 CHECK (is_main IN (0, 1)),
        current_balance INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
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
        account_id INTEGER REFERENCES accounts(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "holdings": """
    CREATE TABLE holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER REFERENCES accounts(id),
        symbol TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        average_price INTEGER NOT NULL DEFAULT 0 CHECK (average_price >= 0),
        invested_amount INTEGER NOT NULL DEFAULT 0 CHECK (invested_amount >= 0),
        market_value INTEGER NOT NULL DEFAULT 0 CHECK (market_value >= 0),
        profit_loss INTEGER NOT NULL DEFAULT 0,
        UNIQUE (account_id, symbol)
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
    "prices": """
    CREATE TABLE prices (
        symbol TEXT PRIMARY KEY,
        price INTEGER NOT NULL CHECK (price >= 0),
        source TEXT NOT NULL DEFAULT 'manual',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # v4: hand-entered positions. The holdings cache is rebuilt from
    # transactions, so manual entries need their own table to survive
    # rebuilds; rebuild_holdings() merges them in. account_id is NOT NULL
    # so the UNIQUE constraint catches duplicates even for a fresh entry
    # (SQLite treats NULLs as distinct in UNIQUE indexes).
    "manual_holdings": """
    CREATE TABLE manual_holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        symbol TEXT NOT NULL,
        quantity REAL NOT NULL CHECK (quantity > 0),
        average_price INTEGER NOT NULL DEFAULT 0 CHECK (average_price >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (account_id, symbol)
    )
    """,
}

# Accounts seeded on first v3 creation. The user's model: a main broker
# account, a main personal account, and the option to add more of either.
_SEED_ACCOUNTS = (
    ("Main broker", "BROKER", 1),
    ("Main personal", "PERSONAL", 1),
)

# Money columns multiplied by 100 during the v1 -> v2 migration, keyed by
# table. Columns not listed here are carried over unchanged.
_MIGRATION_MULTIPLIES = {
    "transactions": ("price", "brokerage", "taxes", "net_amount"),
    "holdings": ("average_price", "invested_amount", "market_value", "profit_loss"),
    "dividends": ("amount",),
}


def ensure_schema():
    """Create tables when missing and migrate older databases in place.

    Fresh database: all tables are created and user_version is set to
    SCHEMA_VERSION. Existing database: each TRANSACTIONS-style table that
    still stores money as REAL is moved aside, recreated with current
    columns, back-filled with amounts multiplied by 100, and the old table
    dropped (v1 path). A v2 database gets the v3 additions in place
    (accounts and prices tables, account_id columns, seeded accounts); a
    v3 database gets the v4 additions (current_balance column,
    manual_holdings table).
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

        _upgrade_to_v3(connection)
        _upgrade_to_v4(connection)

        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _upgrade_to_v3(connection):
    """Add the v3 structures to an existing v2 database, idempotently.

    Structural detection (missing tables/columns) rather than user_version
    alone, so an interrupted upgrade can safely re-run.
    """

    existing = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }

    if "accounts" not in existing:
        connection.execute(_TABLES["accounts"])
    if "prices" not in existing:
        connection.execute(_TABLES["prices"])

    for table in ("transactions", "holdings"):
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if "account_id" not in columns:
            connection.execute(
                f"ALTER TABLE {table} ADD COLUMN account_id "
                "INTEGER REFERENCES accounts(id)"
            )

    seeded = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if not seeded:
        connection.executemany(
            "INSERT INTO accounts (name, kind, is_main) VALUES (?, ?, ?)",
            _SEED_ACCOUNTS,
        )


def _upgrade_to_v4(connection):
    """Add the v4 structures to an existing v3 database, idempotently.

    Structural detection (missing tables/columns) rather than user_version
    alone, so an interrupted upgrade can safely re-run. The accounts table
    gains a user-editable current_balance (defaulting to zero); the
    manual_holdings table stores hand-entered positions that survive
    holdings-cache rebuilds.
    """

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(accounts)")
    }
    if "current_balance" not in columns:
        connection.execute(
            "ALTER TABLE accounts ADD COLUMN current_balance "
            "INTEGER NOT NULL DEFAULT 0"
        )

    existing = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "manual_holdings" not in existing:
        connection.execute(_TABLES["manual_holdings"])


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
