"""Display formatting helpers (pure functions, unit-testable without Tk)."""

INDIAN_GROUPING = True


def format_rupees(amount):
    """Rupee amount as Indian-grouped text: 1234567.5 -> '-₹12,34,567.50'.

    Indian grouping puts the first comma after 3 digits and every 2 digits
    after that (1,23,45,678.90), which is how rupee amounts are read.
    """

    value = round(float(amount or 0), 2)
    sign = "-" if value < 0 else ""
    text = f"{abs(value):.2f}"
    whole, _, fraction = text.partition(".")

    groups = []
    if len(whole) > 3:  # Indian grouping: last 3 digits, then pairs
        groups.append(whole[-3:])
        whole = whole[:-3]
        while len(whole) > 2:
            groups.insert(0, whole[-2:])
            whole = whole[:-2]
    if whole:
        groups.insert(0, whole)

    return f"{sign}₹{','.join(groups)}.{fraction}"


def format_quantity(quantity):
    """Share count without trailing zeros: 17.0 -> '17', 0.5 -> '0.5'."""

    return f"{round(float(quantity or 0), 4):g}"


def kpi_cards(summary):
    """Dashboard cards from get_portfolio_summary(): (label, value, note).

    Market value and profit/loss are zero until the pricing phase supplies
    live prices; the card says so instead of showing a misleading ₹0.00.
    """

    market_value = summary["total_market_value"]
    return [
        ("Total Invested", format_rupees(summary["total_invested"]), "across holdings"),
        ("Holdings", str(summary["total_holdings"]), "open positions"),
        ("Transactions", str(summary["total_transactions"]), "recorded trades"),
        (
            "Market Value",
            format_rupees(market_value) if market_value else "—",
            "live prices coming soon",
        ),
    ]
