"""Portfolio operations over the SQLite database.

Money amounts are stored in the database as INTEGER paise and converted to
rupees at this API boundary (exact two-decimal rounding). net_amount follows
trade-side semantics: a BUY debits quantity*price plus charges; a SELL
credits quantity*price minus charges. The holdings table is a derived cache;
rebuild_holdings() recomputes it from transactions so it cannot drift.
"""

from collections import namedtuple

from database.db import create_connection, execute_query, fetch_all, transaction
from calculations.fno import normalize_fno_symbol
from calculations.holdings import calculate_holdings

PAISE_PER_RUPEE = 100

# Sentinel account filter: rows with account_id IS NULL ("Unassigned").
# Real account ids come from the accounts table (positive integers), so a
# negative sentinel can never collide.
UNASSIGNED = -1


def _account_filter(account_id, column="account_id"):
    """SQL fragment + params for an account scope.

    None -> every account; UNASSIGNED -> account_id IS NULL; otherwise an
    equality on the given account id.
    """

    if account_id is None:
        return "", ()
    if account_id == UNASSIGNED:
        return f"WHERE {column} IS NULL", ()
    return f"WHERE {column} = ?", (account_id,)

# One rebuilt holdings row, before it is written to the cache.
RebuiltHolding = namedtuple(
    "RebuiltHolding",
    ("account_id", "symbol", "quantity", "average_price",
     "invested_amount", "market_value", "profit_loss"),
)

TRANSACTION_MONEY_COLUMNS = ("price", "brokerage", "taxes", "net_amount")
HOLDING_MONEY_COLUMNS = ("average_price", "invested_amount", "market_value", "profit_loss")


def _to_paise(amount):
    """Rupee amount to exact INTEGER paise (None counts as zero)."""

    return int(round(float(amount or 0) * PAISE_PER_RUPEE))


def _from_paise(paise):
    """INTEGER paise back to rupees with exact two-decimal rounding."""

    return round(paise / PAISE_PER_RUPEE, 2)


def _net_amount_paise(transaction_type, quantity, price, brokerage, taxes):
    """Compute net_amount in paise using trade-side semantics.

    BUY:  quantity*price + brokerage + taxes  (what left your account)
    SELL: quantity*price - brokerage - taxes  (what reached your account)
    """

    if transaction_type not in ("BUY", "SELL"):
        raise ValueError(
            f"unsupported transaction type {transaction_type!r}; expected BUY or SELL"
        )

    gross = quantity * price  # units times paise stays paise
    charges = brokerage + taxes
    if transaction_type == "BUY":
        return int(round(gross + charges))
    return int(round(gross - charges))


def add_transaction(
    trade_date,
    symbol,
    isin,
    exchange,
    transaction_type,
    quantity,
    price,
    brokerage=0,
    taxes=0,
):
    """Insert one transaction. Money arguments are rupee amounts."""

    price_paise = _to_paise(price)
    brokerage_paise = _to_paise(brokerage)
    taxes_paise = _to_paise(taxes)
    net_amount = _net_amount_paise(
        transaction_type, quantity, price_paise, brokerage_paise, taxes_paise
    )

    query = """
    INSERT INTO transactions (
        trade_date,
        symbol,
        isin,
        exchange,
        transaction_type,
        quantity,
        price,
        brokerage,
        taxes,
        net_amount
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        trade_date,
        symbol,
        isin,
        exchange,
        transaction_type,
        quantity,
        price_paise,
        brokerage_paise,
        taxes_paise,
        net_amount,
    )

    with transaction() as connection:
        connection.execute(query, params)


def add_transactions(rows, account_id=None):
    """Insert many transactions atomically and return the count processed.

    Each row is a mapping with add_transaction's keywords (brokerage and
    taxes optional, default zero). account_id tags the whole batch with
    one account (None leaves it unassigned). The whole batch commits
    together: a failing row rolls back every row in the batch.
    """

    rows = list(rows)
    inserts = []
    for row in rows:
        price_paise = _to_paise(row["price"])
        brokerage_paise = _to_paise(row.get("brokerage", 0))
        taxes_paise = _to_paise(row.get("taxes", 0))
        inserts.append((
            row["trade_date"],
            row["symbol"],
            row.get("isin"),
            row.get("exchange"),
            row["transaction_type"],
            row["quantity"],
            price_paise,
            brokerage_paise,
            taxes_paise,
            _net_amount_paise(
                row["transaction_type"], row["quantity"], price_paise,
                brokerage_paise, taxes_paise,
            ),
            account_id,
        ))

    with transaction() as connection:
        connection.executemany(
            """
            INSERT INTO transactions (
                trade_date, symbol, isin, exchange, transaction_type,
                quantity, price, brokerage, taxes, net_amount, account_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            inserts,
        )
    return len(rows)


def delete_transaction(transaction_id):
    """Delete one transaction by id. Returns True when a row was removed."""

    with transaction() as connection:
        cursor = connection.execute(
            "DELETE FROM transactions WHERE id = ?", (transaction_id,)
        )
        return cursor.rowcount > 0


def get_transactions(account_id=None):
    """Transactions, newest trade date first, money in rupees.

    account_id filters to one account (UNASSIGNED for account-less rows);
    None means every account.
    """

    fragment, params = _account_filter(account_id)
    query = f"SELECT * FROM transactions {fragment} ORDER BY trade_date DESC"

    return [
        _to_rupees(row, TRANSACTION_MONEY_COLUMNS)
        for row in fetch_all(query, params)
    ]


def _to_rupees(row, money_columns):
    """Copy a database row to a dict, converting money columns to rupees."""

    values = dict(row)
    for column in money_columns:
        values[column] = _from_paise(values[column])
    return values


def update_holding(
    symbol,
    quantity,
    average_price,
    invested_amount,
    market_value=0,
    profit_loss=0,
):
    """Insert or update one holdings row. Money arguments are rupee amounts.

    Updates every holdings row for the symbol (across accounts); inserts
    an Unassigned row when none exists. A rebuild overwrites manual edits.
    """

    symbol = str(symbol or "").strip().upper()
    with transaction() as connection:
        cursor = connection.execute(
            """
            UPDATE holdings
            SET quantity = ?, average_price = ?, invested_amount = ?,
                market_value = ?, profit_loss = ?
            WHERE symbol = ?
            """,
            (
                quantity,
                _to_paise(average_price),
                _to_paise(invested_amount),
                _to_paise(market_value),
                _to_paise(profit_loss),
                symbol,
            ),
        )
        if cursor.rowcount == 0:
            connection.execute(
                """
                INSERT INTO holdings (
                    account_id, symbol, quantity, average_price,
                    invested_amount, market_value, profit_loss
                )
                VALUES (NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    quantity,
                    _to_paise(average_price),
                    _to_paise(invested_amount),
                    _to_paise(market_value),
                    _to_paise(profit_loss),
                ),
            )


def rebuild_holdings():
    """Recompute the holdings cache from transactions and return it.

    Deletes every holdings row and rewrites the current positions from
    calculate_holdings(), so fully sold symbols disappear too. Holdings
    are per account: transactions are grouped by account_id (None =
    Unassigned) and each group aggregates independently.

    Transaction symbols are canonicalized first (F&O text to one shape,
    then the symbol_aliases table), so the same instrument imported under
    different verbatim names forms one holding. The transactions table
    keeps its verbatim symbols; canonicalization affects only aggregation.

    Stored market prices (the prices table) fill market_value and
    profit_loss; symbols without a stored price keep them at zero.
    """

    groups = {}
    for row in _canonicalized_transactions():
        groups.setdefault(row.get("account_id"), []).append(row)

    priced = get_prices_paise()

    rows_to_insert = []
    rebuilt = []
    for account_id, group in groups.items():
        for holding in calculate_holdings(group):
            price_paise = priced.get(holding.symbol.upper())
            if price_paise is None:
                market_value = 0
                profit_loss = 0
            else:
                market_value = int(round(holding.quantity * price_paise))
                profit_loss = market_value - _to_paise(holding.invested_amount)
            row = RebuiltHolding(
                account_id=account_id,
                symbol=holding.symbol,
                quantity=holding.quantity,
                average_price=_to_paise(holding.average_price),
                invested_amount=_to_paise(holding.invested_amount),
                market_value=market_value,
                profit_loss=profit_loss,
            )
            rebuilt.append(row)
            rows_to_insert.append(tuple(row))

    with transaction() as connection:
        connection.execute("DELETE FROM holdings")
        connection.executemany(
            """
            INSERT INTO holdings (
                account_id, symbol, quantity, average_price,
                invested_amount, market_value, profit_loss
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
    return rebuilt


def get_holdings(account_id=None):
    """Holdings rows, symbols ascending, money in rupees, with account name.

    account_id filters to one account (UNASSIGNED for account-less rows);
    None means every account.
    """

    fragment, params = _account_filter(account_id, "holdings.account_id")
    query = f"""
    SELECT holdings.*, accounts.name AS account_name
    FROM holdings LEFT JOIN accounts ON accounts.id = holdings.account_id
    {fragment}
    """
    query += " ORDER BY holdings.symbol ASC"

    return [
        _to_rupees(row, HOLDING_MONEY_COLUMNS)
        for row in fetch_all(query, params)
    ]


def apply_prices_to_holdings():
    """Refresh market_value/profit_loss from stored prices, in place.

    Called after set_price so a new price lights up the existing cache
    without a full rebuild. Symbols without a stored price keep zeros.
    """

    priced = get_prices_paise()
    if not priced:
        return

    updates = []
    for row in fetch_all("SELECT id, symbol, quantity, invested_amount FROM holdings"):
        price_paise = priced.get(str(row["symbol"]).upper())
        if price_paise is None:
            continue
        market_value = int(round(row["quantity"] * price_paise))
        updates.append((market_value, market_value - row["invested_amount"], row["id"]))

    if not updates:
        return

    with transaction() as connection:
        connection.executemany(
            "UPDATE holdings SET market_value = ?, profit_loss = ? WHERE id = ?",
            updates,
        )


# ---------------------------------------------------------------- accounts #


def add_account(name, kind):
    """Create an account (BROKER or PERSONAL) and return its id."""

    kind = str(kind or "").strip().upper()
    if kind not in ("BROKER", "PERSONAL"):
        raise ValueError("account kind must be BROKER or PERSONAL")

    name = str(name or "").strip()
    if not name:
        raise ValueError("account name must not be empty")

    existing = find_account_by_name(name)
    if existing is not None:
        raise ValueError(f"account '{name}' already exists")

    with transaction() as connection:
        cursor = connection.execute(
            "INSERT INTO accounts (name, kind, is_main) VALUES (?, ?, 0)",
            (name, kind),
        )
        return cursor.lastrowid


def get_accounts():
    """All accounts with their transaction counts, mains first."""

    return fetch_all(
        """
        SELECT accounts.*,
               (SELECT COUNT(*) FROM transactions t
                WHERE t.account_id = accounts.id) AS transaction_count
        FROM accounts
        ORDER BY accounts.is_main DESC, accounts.name ASC
        """
    )


def find_account_by_name(name):
    """Account row by case-insensitive name, or None."""

    rows = fetch_all(
        "SELECT * FROM accounts WHERE UPPER(name) = UPPER(?) LIMIT 1",
        (str(name or "").strip(),),
    )
    return rows[0] if rows else None


# ------------------------------------------------------------------ prices #


def set_price(symbol, price, source="manual"):
    """Store the latest price for a holding symbol (rupee amount).

    Upsert by symbol (upper-cased, matching how holdings are keyed).
    Refreshes the holdings cache valuation afterwards so the new price
    is visible immediately.
    """

    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise ValueError("price symbol must not be empty")

    price_paise = _to_paise(price)
    if price_paise < 0:
        raise ValueError("price must not be negative")

    with transaction() as connection:
        connection.execute(
            """
            INSERT INTO prices (symbol, price, source, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(symbol) DO UPDATE SET
                price = excluded.price,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (symbol, price_paise, source),
        )

    apply_prices_to_holdings()


def get_prices_paise():
    """Stored prices as {symbol: paise} for valuation math."""

    return {
        row["symbol"]: row["price"]
        for row in fetch_all("SELECT symbol, price FROM prices")
    }


def get_prices():
    """Stored prices as rows (symbol, rupee price, source, updated_at)."""

    return [
        _to_rupees(row, ("price",))
        for row in fetch_all(
            "SELECT symbol, price, source, updated_at FROM prices ORDER BY symbol"
        )
    ]


def get_symbol_aliases():
    """All alias -> canonical mappings, aliases ascending."""

    return fetch_all("SELECT alias, canonical FROM symbol_aliases ORDER BY alias")


def set_symbol_alias(alias, canonical):
    """Map one verbatim symbol variant onto its canonical holding symbol.

    Aliases are single-level, which rules out chains and cycles by
    construction: the alias key may not already be in use as a canonical
    target, and the canonical target may not itself be an alias key. Both
    names are normalized to upper case like every stored symbol.
    """

    alias_value = str(alias or "").strip().upper()
    canonical_value = str(canonical or "").strip().upper()
    if not alias_value or not canonical_value:
        raise ValueError("alias and canonical symbol must not be empty")
    if alias_value == canonical_value:
        raise ValueError(
            f"alias '{alias_value}' cannot map to itself"
        )
    if _is_canonical_value(alias_value):
        raise ValueError(
            f"'{alias_value}' is already a canonical target of another "
            "alias; mapping it again would create a chain (no chains)"
        )
    if _is_alias(canonical_value):
        raise ValueError(
            f"canonical '{canonical_value}' is itself an alias; "
            "aliases must map directly to a final symbol (no chains)"
        )

    execute_query(
        """
        INSERT INTO symbol_aliases (alias, canonical) VALUES (?, ?)
        ON CONFLICT(alias) DO UPDATE SET canonical = excluded.canonical
        """,
        (alias_value, canonical_value),
    )


def delete_symbol_alias(alias):
    """Remove one alias mapping."""

    execute_query("DELETE FROM symbol_aliases WHERE alias = ?", (
        str(alias or "").strip().upper(),
    ))


def canonical_symbol(symbol):
    """The canonical name for a symbol (alias table lookup, else unchanged)."""

    row = fetch_all(
        "SELECT canonical FROM symbol_aliases WHERE alias = ?",
        (str(symbol or "").strip().upper(),),
    )
    return row[0]["canonical"] if row else str(symbol or "").strip().upper()


def _is_alias(symbol):
    return bool(fetch_all(
        "SELECT 1 FROM symbol_aliases WHERE alias = ? LIMIT 1",
        (str(symbol).strip().upper(),),
    ))


def _is_canonical_value(symbol):
    return bool(fetch_all(
        "SELECT 1 FROM symbol_aliases WHERE canonical = ? LIMIT 1",
        (str(symbol).strip().upper(),),
    ))


def _canonicalized_transactions():
    """Transactions with symbols normalized and mapped through aliases.

    F&O text is first brought to one canonical shape (calculations.fno),
    then the alias table maps verbatim equity variants. Returns plain
    dicts (sqlite3.Row is immutable) only when at least one alias exists,
    so the no-alias path stays allocation-free.
    """

    aliases = {row["alias"]: row["canonical"] for row in get_symbol_aliases()}

    def canonicalize(symbol):
        normalized = normalize_fno_symbol(symbol)
        text = normalized if normalized is not None else str(symbol or "")
        return aliases.get(text.upper()) or text

    if not aliases:
        return [
            {**row, "symbol": canonicalize(row["symbol"])}
            for row in get_transactions()
        ]

    canonicalized = []
    for row in get_transactions():
        item = dict(row)
        item["symbol"] = canonicalize(item["symbol"])
        canonicalized.append(item)
    return canonicalized


def add_dividend(symbol, dividend_date, amount):
    """Record a dividend. Amount is a rupee amount."""

    query = """
    INSERT INTO dividends (
        symbol,
        dividend_date,
        amount
    )
    VALUES (?, ?, ?)
    """

    with transaction() as connection:
        connection.execute(query, (symbol, dividend_date, _to_paise(amount)))


def get_dividends():
    """All dividend rows, newest first, amount in rupees."""

    return [
        _to_rupees(row, ("amount",))
        for row in fetch_all("SELECT * FROM dividends ORDER BY dividend_date DESC")
    ]


def add_import(filename, import_type, status):
    """Record one import attempt."""

    query = """
    INSERT INTO imports (
        filename,
        import_type,
        status
    )
    VALUES (?, ?, ?)
    """

    with transaction() as connection:
        connection.execute(query, (filename, import_type, status))


def get_imports(import_type=None):
    """Import-audit rows, newest first, optionally one import_type only."""

    if import_type is None:
        return fetch_all("SELECT * FROM imports ORDER BY imported_date DESC")
    return fetch_all(
        "SELECT * FROM imports WHERE import_type = ? "
        "ORDER BY imported_date DESC",
        (import_type,),
    )


def get_portfolio_summary(account_id=None):
    """Aggregate counts and rupee totals from the holdings cache.

    account_id scopes the numbers to one account (UNASSIGNED for
    account-less rows); None means every account.
    """

    holding_filter, params = _account_filter(account_id)
    transaction_filter, _ = _account_filter(account_id)

    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute(f"SELECT COUNT(*) FROM transactions {transaction_filter}", params)
    total_transactions = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM holdings {holding_filter}", params)
    total_holdings = cursor.fetchone()[0]

    cursor.execute(
        f"SELECT COALESCE(SUM(invested_amount), 0) FROM holdings {holding_filter}",
        params,
    )
    total_invested = _from_paise(cursor.fetchone()[0])

    cursor.execute(
        f"SELECT COALESCE(SUM(market_value), 0) FROM holdings {holding_filter}",
        params,
    )
    total_market_value = _from_paise(cursor.fetchone()[0])

    cursor.execute(
        f"SELECT COALESCE(SUM(profit_loss), 0) FROM holdings {holding_filter}",
        params,
    )
    total_profit_loss = _from_paise(cursor.fetchone()[0])

    connection.close()

    return {
        "total_transactions": total_transactions,
        "total_holdings": total_holdings,
        "total_invested": total_invested,
        "total_market_value": total_market_value,
        "total_profit_loss": total_profit_loss,
    }


if __name__ == "__main__":
    print(get_portfolio_summary())
