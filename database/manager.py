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

    Hand-entered positions (manual_holdings) are merged in afterwards:
    'manual' rows add their quantity to any transaction-derived position
    for the same (account, symbol); 'holding_report' rows (imported
    broker statements) replace the transaction-derived row outright.
    """

    groups = {}
    for row in _canonicalized_transactions():
        groups.setdefault(row.get("account_id"), []).append(row)

    priced = get_prices_paise()

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

    rebuilt = _merge_manual_holdings(rebuilt, priced)
    rows_to_insert = [tuple(row) for row in rebuilt]

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
    """All accounts with transaction counts and balance, mains first.

    current_balance is converted to rupees; everything else is raw.
    """

    return [
        _to_rupees(row, ("current_balance",))
        for row in fetch_all(
            """
            SELECT accounts.*,
                   (SELECT COUNT(*) FROM transactions t
                    WHERE t.account_id = accounts.id) AS transaction_count
            FROM accounts
            ORDER BY accounts.is_main DESC, accounts.name ASC
            """
        )
    ]


def find_account_by_name(name):
    """Account row by case-insensitive name, or None."""

    rows = fetch_all(
        "SELECT * FROM accounts WHERE UPPER(name) = UPPER(?) LIMIT 1",
        (str(name or "").strip(),),
    )
    return rows[0] if rows else None


def find_account_by_id(account_id):
    """Account row by id, or None."""

    rows = fetch_all(
        "SELECT * FROM accounts WHERE id = ? LIMIT 1",
        (account_id,),
    )
    return rows[0] if rows else None


def set_account_balance(account_id, rupees):
    """Set an account's user-entered current balance; True when it exists.

    The balance is a hand-entered figure (what the broker statement says),
    independent of the derived invested amounts, so negative values are
    allowed. Money is stored as INTEGER paise.
    """

    amount_paise = _to_paise(rupees)
    with transaction() as connection:
        cursor = connection.execute(
            "UPDATE accounts SET current_balance = ? WHERE id = ?",
            (amount_paise, account_id),
        )
    return cursor.rowcount > 0


# Account detail fields the user can fill by hand or that importers can
# auto-fill from files (UCC from a broker holdings statement, PAN from a
# statement header, account number and phone from a bank statement).
ACCOUNT_DETAIL_FIELDS = ("holder_name", "account_number", "phone", "pan", "ucc")


def update_account_details(account_id, holder_name=None, account_number=None,
                           phone=None, pan=None, ucc=None):
    """Update account detail fields; only supplied values are changed.

    Each argument maps to one accounts column; pass only the fields you
    want to change (empty string clears a field). Returns True when the
    account exists, False otherwise.
    """

    updates = {
        "holder_name": holder_name,
        "account_number": account_number,
        "phone": phone,
        "pan": pan,
        "ucc": ucc,
    }
    updates = {
        name: (str(value).strip() if value is not None else None)
        for name, value in updates.items()
        if value is not None
    }
    if not updates:
        return find_account_by_id(account_id) is not None

    set_clause = ", ".join(f"{name} = ?" for name in updates)
    params = list(updates.values()) + [account_id]

    with transaction() as connection:
        cursor = connection.execute(
            f"UPDATE accounts SET {set_clause} WHERE id = ?",
            params,
        )
    return cursor.rowcount > 0


def fill_account_details_if_empty(account_id, **fields):
    """Auto-fill account detail fields that are currently empty.

    Used by importers: a file carries details like a UCC or PAN, and
    those fill any account field still empty. Fields the user already
    filled are never overwritten. Returns the dict of fields actually
    filled.
    """

    account = find_account_by_id(account_id)
    if account is None:
        return {}

    filled = {}
    updates = {}
    for name, value in fields.items():
        if name not in ACCOUNT_DETAIL_FIELDS or value is None:
            continue
        value = str(value).strip()
        if value and not (account[name] or "").strip():
            updates[name] = value
            filled[name] = value

    if updates:
        set_clause = ", ".join(f"{name} = ?" for name in updates)
        params = list(updates.values()) + [account_id]
        with transaction() as connection:
            connection.execute(
                f"UPDATE accounts SET {set_clause} WHERE id = ?",
                params,
            )
    return filled


# --------------------------------------------------------- manual holdings #


def add_manual_holding(account_id, symbol, quantity, average_price,
                       source="manual"):
    """Record a hand-entered holding (rupee average price).

    Manual rows live in their own table and are merged into the holdings
    cache by rebuild_holdings(), so they survive cache rebuilds. Re-adding
    the same (account, symbol) replaces the earlier entry. source decides
    the merge semantics: 'manual' rows add to transaction-derived
    positions, snapshot rows ('holding_report', 'mf_holding_report')
    replace them.
    """

    if source not in ("manual", "holding_report", "mf_holding_report"):
        raise ValueError(f"unsupported holding source {source!r}")

    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise ValueError("symbol must not be empty")

    quantity = float(quantity or 0)
    if not quantity > 0:
        raise ValueError("quantity must be greater than zero")

    average_price = float(average_price or 0)
    if average_price < 0:
        raise ValueError("average price cannot be negative")

    if find_account_by_id(account_id) is None:
        raise ValueError(f"account id {account_id} does not exist")

    with transaction() as connection:
        connection.execute(
            """
            INSERT INTO manual_holdings (account_id, symbol, quantity,
                                         average_price, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account_id, symbol) DO UPDATE SET
                quantity = excluded.quantity,
                average_price = excluded.average_price,
                source = excluded.source
            """,
            (account_id, symbol, quantity, _to_paise(average_price), source),
        )


def replace_holding_report(rows, account_id, source="holding_report"):
    """Atomically replace the account's snapshot rows for one source.

    Deletes every row of the given source for the account before
    inserting the new snapshot, so a fresher report cannot leave stale
    symbols behind (a symbol sold since the last report disappears).
    source is 'holding_report' (stock statements) or
    'mf_holding_report' (mutual-fund statements); the two are replaced
    independently, so importing one never wipes the other. User-added
    'manual' rows are untouched; a snapshot row for a manually-added
    symbol replaces it (the report wins).
    Rows are mappings with symbol, quantity, average_price (rupees).
    Returns the number of rows stored.
    """

    if source not in ("holding_report", "mf_holding_report"):
        raise ValueError(f"unsupported holding-report source {source!r}")

    if find_account_by_id(account_id) is None:
        raise ValueError("holding reports must be assigned to an existing account")

    prepared = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("every holding row needs a symbol")
        quantity = float(row.get("quantity") or 0)
        if not quantity > 0:
            raise ValueError(f"quantity for {symbol} must be greater than zero")
        average_price = float(row.get("average_price") or 0)
        if average_price < 0:
            raise ValueError(f"average price for {symbol} cannot be negative")
        prepared.append((account_id, symbol, quantity, _to_paise(average_price)))

    with transaction() as connection:
        connection.execute(
            "DELETE FROM manual_holdings "
            "WHERE account_id = ? AND source = ?",
            (account_id, source),
        )
        connection.executemany(
            """
            INSERT INTO manual_holdings (account_id, symbol, quantity,
                                         average_price, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account_id, symbol) DO UPDATE SET
                quantity = excluded.quantity,
                average_price = excluded.average_price,
                source = excluded.source
            """,
            [(account_id, symbol, quantity, average_paise, source)
             for account_id, symbol, quantity, average_paise in prepared],
        )
    return len(prepared)


def get_manual_holdings(account_id=None):
    """Manual holdings rows, symbols ascending, money in rupees, with account.

    account_id filters to one account (UNASSIGNED matches nothing, since
    manual rows always belong to an account); None means every account.
    """

    fragment, params = _account_filter(account_id, "manual_holdings.account_id")
    query = f"""
    SELECT manual_holdings.*, accounts.name AS account_name
    FROM manual_holdings
    LEFT JOIN accounts ON accounts.id = manual_holdings.account_id
    {fragment}
    """
    query += " ORDER BY manual_holdings.symbol ASC"

    return [
        _to_rupees(row, ("average_price",))
        for row in fetch_all(query, params)
    ]


def delete_manual_holding(manual_id):
    """Delete one manual holding row; True when a row was removed."""

    with transaction() as connection:
        cursor = connection.execute(
            "DELETE FROM manual_holdings WHERE id = ?",
            (manual_id,),
        )
    return cursor.rowcount > 0


def _merge_manual_holdings(rebuilt, priced):
    """Fold manual_holdings rows into the rebuilt cache; returns the merge.

    Semantics by source:

    - 'manual': the user added a position by hand, so its quantity adds
      to any transaction-derived position for the same (account, canonical
      symbol) — invested grows by quantity x average and the average price
      recomputes weighted. Unmatched manual symbols become new rows.
    - snapshot sources ('holding_report', 'mf_holding_report'): the
      statement is the authoritative CURRENT position, so it replaces the
      transaction-derived row outright (the report knows about sells the
      contract notes may not).

    Manual symbols are canonicalized like transaction symbols; the
    manual_holdings table keeps its verbatim symbol.
    """

    by_key = {(row.account_id, row.symbol): row for row in rebuilt}

    for manual in fetch_all(
        "SELECT account_id, symbol, quantity, average_price, source "
        "FROM manual_holdings"
    ):
        symbol = canonical_symbol(manual["symbol"])
        key = (manual["account_id"], symbol)
        quantity = manual["quantity"]
        invested_paise = int(round(quantity * manual["average_price"]))

        price_paise = priced.get(symbol.upper())
        if price_paise is None:
            market_value = 0
            profit_loss = 0
        else:
            market_value = int(round(quantity * price_paise))
            profit_loss = market_value - invested_paise

        if manual["source"] != "manual":
            by_key[key] = RebuiltHolding(
                account_id=manual["account_id"],
                symbol=symbol,
                quantity=quantity,
                average_price=manual["average_price"],
                invested_amount=invested_paise,
                market_value=market_value,
                profit_loss=profit_loss,
            )
            continue

        existing = by_key.get(key)
        if existing is None:
            by_key[key] = RebuiltHolding(
                account_id=manual["account_id"],
                symbol=symbol,
                quantity=quantity,
                average_price=manual["average_price"],
                invested_amount=invested_paise,
                market_value=market_value,
                profit_loss=profit_loss,
            )
            continue

        total_quantity = existing.quantity + quantity
        total_invested = existing.invested_amount + invested_paise
        if price_paise is None:
            market_value = 0
            profit_loss = 0
        else:
            market_value = int(round(total_quantity * price_paise))
            profit_loss = market_value - total_invested

        by_key[key] = RebuiltHolding(
            account_id=existing.account_id,
            symbol=existing.symbol,
            quantity=total_quantity,
            average_price=int(round(total_invested / total_quantity)),
            invested_amount=total_invested,
            market_value=market_value,
            profit_loss=profit_loss,
        )

    return list(by_key.values())


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


# ------------------------------------------------------- bank transactions #


def add_bank_transactions(rows, account_id):
    """Insert bank-statement transaction lines; skip rows already stored.

    Rows are mappings with txn_date (ISO text), description (non-empty),
    amount (signed rupees: credit positive, debit negative) and balance
    (rupees after the transaction). A row identical to one already stored
    for the account (same date, description, amount and balance) is
    skipped, so re-imports and overlapping statement periods are
    idempotent. Returns (imported, duplicates).
    """

    if find_account_by_id(account_id) is None:
        raise ValueError(
            "bank transactions must belong to an existing account"
        )

    prepared = []
    for row in rows:
        txn_date = str(row.get("txn_date") or "").strip()
        if not txn_date:
            raise ValueError("every bank transaction needs a date")
        description = str(row.get("description") or "").strip()
        if not description:
            raise ValueError("every bank transaction needs a description")
        amount = float(row.get("amount") or 0)
        if amount == 0:
            raise ValueError(
                f"bank transaction '{description}' has a zero amount"
            )
        balance = float(row.get("balance") or 0)
        prepared.append((
            txn_date,
            description,
            _to_paise(amount),
            _to_paise(balance),
        ))

    existing = {
        (row["txn_date"], row["description"], row["amount"], row["balance"])
        for row in get_bank_transactions(account_id=account_id, _raw=True)
    }

    fresh = [entry for entry in prepared if entry not in existing]
    with transaction() as connection:
        connection.executemany(
            """
            INSERT INTO bank_transactions (
                account_id, txn_date, description, amount, balance
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [(account_id, *entry) for entry in fresh],
        )
    return len(fresh), len(prepared) - len(fresh)


def get_bank_transactions(account_id=None, _raw=False):
    """Bank transactions, chronological, money in rupees (paise when _raw).

    account_id filters to one account; None means every account. The
    _raw flag is for internal dedup lookups (values stay paise integers).
    """

    fragment, params = _account_filter(account_id, "bank_transactions.account_id")
    query = f"""
    SELECT bank_transactions.*, accounts.name AS account_name
    FROM bank_transactions
    LEFT JOIN accounts ON accounts.id = bank_transactions.account_id
    {fragment}
    ORDER BY bank_transactions.txn_date ASC, bank_transactions.id ASC
    """

    rows = fetch_all(query, params)
    if _raw:
        return rows
    return [
        _to_rupees(row, ("amount", "balance"))
        for row in rows
    ]


def count_bank_transactions(account_id=None):
    """Number of stored bank transactions, optionally for one account."""

    fragment, params = _account_filter(account_id, "account_id")
    with transaction() as connection:
        row = connection.execute(
            f"SELECT COUNT(*) FROM bank_transactions {fragment}",
            params,
        ).fetchone()
    return row[0]


# ------------------------------------------------------- stock metadata #


def set_stock_metadata(symbol, sector=None, market_cap=None, source="yahoo"):
    """Upsert one symbol's cached metadata (sector, market cap in rupees).

    market_cap is a rupee figure stored as INTEGER rupees (or None for
    funds / ETFs / derivatives, which have no market capitalization).
    Returns the stored row.
    """

    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise ValueError("stock metadata needs a symbol")

    cap = None if market_cap is None else int(round(float(market_cap)))
    with transaction() as connection:
        connection.execute(
            """
            INSERT INTO stock_metadata (symbol, sector, market_cap, source)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                sector = excluded.sector,
                market_cap = excluded.market_cap,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (symbol, sector, cap, source),
        )
    return find_stock_metadata(symbol)


def find_stock_metadata(symbol):
    """One symbol's metadata row, or None."""

    symbol = str(symbol or "").strip().upper()
    rows = fetch_all(
        "SELECT symbol, sector, market_cap, source, updated_at "
        "FROM stock_metadata WHERE symbol = ?",
        (symbol,),
    )
    return rows[0] if rows else None


def get_stock_metadata():
    """All cached stock metadata rows, symbols ascending."""

    return fetch_all(
        "SELECT symbol, sector, market_cap, source, updated_at "
        "FROM stock_metadata ORDER BY symbol"
    )


# ------------------------------------------------------- stock metadata #


def set_stock_metadata(symbol, sector=None, market_cap=None, source="yahoo"):
    """Upsert one symbol's cached metadata (sector, market cap in rupees).

    market_cap is a rupee figure stored as INTEGER rupees (or None for
    funds / ETFs / derivatives, which have no market capitalization).
    Returns the stored row.
    """

    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise ValueError("stock metadata needs a symbol")

    cap = None if market_cap is None else int(round(float(market_cap)))
    with transaction() as connection:
        connection.execute(
            """
            INSERT INTO stock_metadata (symbol, sector, market_cap, source)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                sector = excluded.sector,
                market_cap = excluded.market_cap,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (symbol, sector, cap, source),
        )
    return find_stock_metadata(symbol)


def find_stock_metadata(symbol):
    """One symbol's metadata row, or None."""

    symbol = str(symbol or "").strip().upper()
    rows = fetch_all(
        "SELECT symbol, sector, market_cap, source, updated_at "
        "FROM stock_metadata WHERE symbol = ?",
        (symbol,),
    )
    return rows[0] if rows else None


def get_stock_metadata():
    """All cached stock metadata rows, symbols ascending."""

    return fetch_all(
        "SELECT symbol, sector, market_cap, source, updated_at "
        "FROM stock_metadata ORDER BY symbol"
    )


if __name__ == "__main__":
    print(get_portfolio_summary())
