from database.db import create_connection


def create_tables():
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT,
        symbol TEXT,
        isin TEXT,
        exchange TEXT,
        transaction_type TEXT,
        quantity REAL,
        price REAL,
        brokerage REAL DEFAULT 0,
        taxes REAL DEFAULT 0,
        net_amount REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE,
        quantity REAL,
        average_price REAL,
        invested_amount REAL,
        market_value REAL DEFAULT 0,
        profit_loss REAL DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dividends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        dividend_date TEXT,
        amount REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        import_type TEXT,
        imported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT
    )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully")
