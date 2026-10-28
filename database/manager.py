"""Portfolio operations over the SQLite database.

Money amounts are stored in the database as INTEGER paise and converted to
rupees at this API boundary (exact two-decimal rounding). net_amount follows
trade-side semantics: a BUY debits quantity*price plus charges; a SELL
credits quantity*price minus charges. The holdings table is a derived cache;
rebuild_holdings() recomputes it from transactions so it cannot drift.
"""

from database.db import create_connection, execute_query, fetch_all, transaction
from calculations.holdings import calculate_holdings

PAISE_PER_RUPEE = 100

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


def add_transactions(rows):
    """Insert many transactions atomically and return the count processed.

    Each row is a mapping with add_transaction's keywords (brokerage and
    taxes optional, default zero). The whole batch commits together: a
    failing row rolls back every row in the batch.
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
        ))

    with transaction() as connection:
        connection.executemany(
            """
            INSERT INTO transactions (
                trade_date, symbol, isin, exchange, transaction_type,
                quantity, price, brokerage, taxes, net_amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def get_transactions():
    """All transactions, newest trade date first, money in rupees."""

    return [
        _to_rupees(row, TRANSACTION_MONEY_COLUMNS)
        for row in fetch_all("SELECT * FROM transactions ORDER BY trade_date DESC")
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
    """Insert or update one holdings row. Money arguments are rupee amounts."""

    query = """
    INSERT INTO holdings (
        symbol,
        quantity,
        average_price,
        invested_amount,
        market_value,
        profit_loss
    )
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(symbol) DO UPDATE SET
        quantity = excluded.quantity,
        average_price = excluded.average_price,
        invested_amount = excluded.invested_amount,
        market_value = excluded.market_value,
        profit_loss = excluded.profit_loss
    """

    params = (
        symbol,
        quantity,
        _to_paise(average_price),
        _to_paise(invested_amount),
        _to_paise(market_value),
        _to_paise(profit_loss),
    )

    with transaction() as connection:
        connection.execute(query, params)


def rebuild_holdings():
    """Recompute the holdings cache from transactions and return it.

    Deletes every holdings row and rewrites the current positions from
    calculate_holdings(), so fully sold symbols disappear too. market_value
    and profit_loss reset to zero because they need market prices, which are
    restored when the pricing phase lands. Money is stored in paise.

    Transaction symbols are canonicalized through the symbol_aliases table
    before aggregation, so the same company imported under different
    verbatim names (e.g. VEDANTA and VEDANTA LIMITED from different
    sources) forms one holding. The transactions table keeps its verbatim
    symbols; aliases affect only aggregation.
    """

    holdings = calculate_holdings(_canonicalized_transactions())

    with transaction() as connection:
        connection.execute("DELETE FROM holdings")
        connection.executemany(
            """
            INSERT INTO holdings (
                symbol, quantity, average_price, invested_amount,
                market_value, profit_loss
            )
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            [
                (
                    holding.symbol,
                    holding.quantity,
                    _to_paise(holding.average_price),
                    _to_paise(holding.invested_amount),
                )
                for holding in holdings
            ],
        )
    return holdings


def get_holdings():
    """All holdings rows, symbols ascending, money in rupees."""

    return [
        _to_rupees(row, HOLDING_MONEY_COLUMNS)
        for row in fetch_all("SELECT * FROM holdings ORDER BY symbol ASC")
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
    """Transactions with symbols mapped through the alias table.

    Returns plain dicts (sqlite3.Row is immutable) only when at least one
    alias exists, so the no-alias path stays allocation-free.
    """

    aliases = {row["alias"]: row["canonical"] for row in get_symbol_aliases()}
    if not aliases:
        return get_transactions()

    canonicalized = []
    for row in get_transactions():
        item = dict(row)
        mapped = aliases.get(str(item["symbol"]).upper())
        if mapped:
            item["symbol"] = mapped
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


def get_portfolio_summary():
    """Aggregate counts and rupee totals from the holdings cache."""

    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM holdings")
    total_holdings = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(invested_amount), 0) FROM holdings")
    total_invested = _from_paise(cursor.fetchone()[0])

    cursor.execute("SELECT COALESCE(SUM(market_value), 0) FROM holdings")
    total_market_value = _from_paise(cursor.fetchone()[0])

    cursor.execute("SELECT COALESCE(SUM(profit_loss), 0) FROM holdings")
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
