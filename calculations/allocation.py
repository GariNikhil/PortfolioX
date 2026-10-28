"""Portfolio allocation and tax-period summaries (pure functions).

These feed the dashboard's Portfolio Analysis section and the Tax page.
They take plain dict rows shaped like database.manager's getters return
(amounts in rupees) so they are unit-testable without a database.
"""

from collections import defaultdict

from calculations.fno import normalize_fno_symbol


def asset_allocation(holdings):
    """Split holdings into asset classes by invested amount (rupees).

    Equity vs F&O for now: a holding whose symbol parses as an F&O
    contract counts as F&O, everything else as Equity. Mutual funds,
    bonds and US stocks arrive with their own importers and will join
    the split then. Returns (label, amount) pairs sorted by amount
    descending, zero classes omitted.
    """

    amounts = defaultdict(float)
    for holding in holdings:
        symbol = str(holding.get("symbol") or "")
        label = "F&O" if normalize_fno_symbol(symbol) else "Equity"
        amounts[label] += float(holding.get("invested_amount") or 0)

    return sorted(
        ((label, amount) for label, amount in amounts.items() if amount),
        key=lambda pair: pair[1],
        reverse=True,
    )


def financial_year_of(trade_date):
    """ISO date 'YYYY-MM-DD' -> the FY label it falls in (April-March).

    FY 2023-24 covers 2023-04-01 .. 2024-03-31.
    """

    year, month = int(trade_date[:4]), int(trade_date[5:7])
    start = year if month >= 4 else year - 1
    return f"FY {start}-{(start + 1) % 100:02d}"


def financial_year_summary(transactions):
    """Per-FY trading summary, newest year first.

    Returns (label, stats) pairs where stats is a dict with buy_count,
    sell_count, buy_turnover and sell_turnover (rupees, gross qty*price
    before charges — the turnover tax reports start from).
    """

    years = {}
    for row in transactions:
        label = financial_year_of(str(row["trade_date"]))
        stats = years.setdefault(label, {
            "buy_count": 0, "sell_count": 0,
            "buy_turnover": 0.0, "sell_turnover": 0.0,
        })
        quantity = float(row["quantity"] or 0)
        gross = quantity * float(row["price"] or 0)
        if str(row["transaction_type"]).upper() == "BUY":
            stats["buy_count"] += 1
            stats["buy_turnover"] += gross
        else:
            stats["sell_count"] += 1
            stats["sell_turnover"] += gross

    return sorted(years.items(), reverse=True)
