"""Report writers: CSV and text exports of holdings and transactions.

Pure functions over the rows returned by database.manager (money already
in rupees). CSV output is machine-readable (raw numbers, ISO dates, no
currency marks); the text report is human-readable with Indian-grouped
rupees. The caller chooses where to save the returned strings.
"""

import csv
import io
from datetime import datetime

from ui.formatting import format_quantity, format_rupees

HOLDINGS_CSV_COLUMNS = (
    "symbol",
    "quantity",
    "average_price",
    "invested_amount",
    "market_value",
    "profit_loss",
)

TRANSACTIONS_CSV_COLUMNS = (
    "trade_date",
    "symbol",
    "transaction_type",
    "quantity",
    "price",
    "brokerage",
    "taxes",
    "net_amount",
)


def holdings_csv(holdings):
    """All holdings as CSV text, symbols ascending (input order)."""

    rows = (
        (
            row["symbol"],
            row["quantity"],
            row["average_price"],
            row["invested_amount"],
            row["market_value"],
            row["profit_loss"],
        )
        for row in holdings
    )
    return _csv_text(HOLDINGS_CSV_COLUMNS, rows)


def transactions_csv(transactions):
    """All transactions as CSV text, newest first (input order)."""

    rows = (
        (
            row["trade_date"],
            row["symbol"],
            row["transaction_type"],
            row["quantity"],
            row["price"],
            row["brokerage"],
            row["taxes"],
            row["net_amount"],
        )
        for row in transactions
    )
    return _csv_text(TRANSACTIONS_CSV_COLUMNS, rows)


def portfolio_text_report(summary, holdings, generated_at=None):
    """Human-readable portfolio summary with Indian-grouped rupees."""

    stamp = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    market_value = summary["total_market_value"]
    lines = [
        f"PortfolioX report - {stamp}",
        "=" * 40,
        "",
        "Summary",
        "-------",
        f"Total invested : {format_rupees(summary['total_invested'])}",
        f"Holdings       : {summary['total_holdings']} open positions",
        f"Transactions   : {summary['total_transactions']} recorded trades",
        (
            f"Market value   : {format_rupees(market_value)}"
            if market_value
            else "Market value   : - (live prices coming soon)"
        ),
        "",
        "Holdings (by invested amount)",
        "-----------------------------",
    ]

    if not holdings:
        lines.append("(no open positions)")
        return "\n".join(lines) + "\n"

    width = max(len(row["symbol"]) for row in holdings)
    for row in sorted(holdings, key=lambda r: r["invested_amount"], reverse=True):
        lines.append(
            f"{row['symbol'].ljust(width)}  "
            f"{format_quantity(row['quantity']).rjust(8)}  "
            f"@ {format_rupees(row['average_price']).rjust(14)}  "
            f"= {format_rupees(row['invested_amount']).rjust(14)}"
        )
    return "\n".join(lines) + "\n"


def _csv_text(columns, rows):
    """Rows through the csv module (quoting handled for us)."""

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()
