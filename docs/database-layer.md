# PortfolioX - Database Layer Documentation (Phase 2)

## Schema Definition

The database uses SQLite with `CREATE TABLE IF NOT EXISTS` for idempotent schema creation.

### Transactions Table
```sql
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    buy_sell TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    status TEXT NOT NULL,
    product TEXT NOT NULL,
    date TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

### Holdings Table
```sql
CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL,
    avg_cost REAL NOT NULL,
    total_value REAL NOT NULL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

### Idempotent Import
- Uses symbol + date + qty as the unique composite key
- Duplicate transactions are skipped silently (no error)
- Import summary reports successes and failures

### CRUD Operations
- `create_connection()`: Establish SQLite connection
- `initiate_db()`: Create tables if they don't exist
- `add_transaction()`: Insert a single transaction
- `get_all_transactions()`: Retrieve all transactions
- `get_transactions_by_symbol()`: Filter by stock symbol

### Connection Management
- DB_PATH: Centralized path constant
- Connection handling with proper cleanup
- Thread-safe access patterns