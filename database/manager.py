from database.db import create_connection, execute_query, fetch_all


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
    net_amount = (quantity * price) + brokerage + taxes

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
        price,
        brokerage,
        taxes,
        net_amount,
    )

    execute_query(query, params)


def get_transactions():
    query = """
    SELECT *
    FROM transactions
    ORDER BY trade_date DESC
    """

    return fetch_all(query)


def update_holding(
    symbol,
    quantity,
    average_price,
    invested_amount,
    market_value=0,
    profit_loss=0,
):
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
        average_price,
        invested_amount,
        market_value,
        profit_loss,
    )

    execute_query(query, params)


def get_holdings():
    query = """
    SELECT *
    FROM holdings
    ORDER BY symbol ASC
    """

    return fetch_all(query)


def add_dividend(symbol, dividend_date, amount):
    query = """
    INSERT INTO dividends (
        symbol,
        dividend_date,
        amount
    )
    VALUES (?, ?, ?)
    """

    params = (symbol, dividend_date, amount)

    execute_query(query, params)


def get_dividends():
    query = """
    SELECT *
    FROM dividends
    ORDER BY dividend_date DESC
    """

    return fetch_all(query)


def add_import(filename, import_type, status):
    query = """
    INSERT INTO imports (
        filename,
        import_type,
        status
    )
    VALUES (?, ?, ?)
    """

    params = (filename, import_type, status)

    execute_query(query, params)


def get_portfolio_summary():
    connection = create_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_transactions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM holdings")
    total_holdings = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(invested_amount), 0) FROM holdings")
    total_invested = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(market_value), 0) FROM holdings")
    total_market_value = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(profit_loss), 0) FROM holdings")
    total_profit_loss = cursor.fetchone()[0]

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