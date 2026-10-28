"""Calculate current positions from BUY and SELL transactions.

The remaining cost basis uses moving weighted-average cost. It is intended for
portfolio summaries, not FIFO accounting or tax reporting.
"""

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Holding:
    symbol: str
    isin: str | None
    exchange: str | None
    quantity: float
    invested_amount: float
    average_price: float


def calculate_holdings(transactions):
    """Return active holdings calculated from transaction rows.

    Rows may be database tuples in the schema's SELECT * order, or mappings
    with the same column names. Rows are processed by trade date and then ID
    (when available), independent of query sort order. Sells reduce remaining
    cost at the position's current average cost. Invalid types, non-finite
    values, and oversells raise ``ValueError`` rather than silently producing
    an inaccurate position.
    """
    positions = defaultdict(lambda: {
        "isin": None,
        "exchange": None,
        "quantity": 0.0,
        "cost": 0.0,
    })

    normalized_transactions = [
        _transaction_fields(row, row_number)
        for row_number, row in enumerate(transactions, start=1)
    ]
    ordered_transactions = sorted(
        normalized_transactions,
        key=lambda trade: (trade.get("trade_date") or "", trade.get("id") or 0),
    )

    for row_number, transaction in enumerate(ordered_transactions, start=1):
        trade = transaction
        symbol_value = trade.get("symbol")
        if not isinstance(symbol_value, str):
            raise ValueError(f"Transaction {row_number}: symbol is required")
        symbol = symbol_value.strip().upper()
        if not symbol:
            raise ValueError(f"Transaction {row_number}: symbol is required")

        transaction_type = str(trade.get("transaction_type") or "").strip().upper()
        if transaction_type not in {"BUY", "SELL"}:
            raise ValueError(
                f"Transaction {row_number}: unsupported transaction type "
                f"{transaction_type!r}; expected BUY or SELL"
            )

        quantity = _number(trade["quantity"], "quantity", row_number)
        price = _number(trade["price"], "price", row_number)
        brokerage = _number(trade["brokerage"] or 0, "brokerage", row_number)
        taxes = _number(trade["taxes"] or 0, "taxes", row_number)
        if quantity <= 0 or price < 0 or brokerage < 0 or taxes < 0:
            raise ValueError(
                f"Transaction {row_number}: quantity must be positive and "
                "price and charges cannot be negative"
            )

        position = positions[symbol]
        position["isin"] = trade["isin"] or position["isin"]
        position["exchange"] = trade["exchange"] or position["exchange"]

        if transaction_type == "BUY":
            position["quantity"] += quantity
            position["cost"] += quantity * price + brokerage + taxes
            continue

        if quantity > position["quantity"] + 1e-9:
            raise ValueError(
                f"Transaction {row_number}: cannot sell {quantity:g} shares "
                f"of {symbol}; only {position['quantity']:g} are held"
            )

        average_cost = position["cost"] / position["quantity"]
        position["quantity"] -= quantity
        position["cost"] -= average_cost * quantity
        if position["quantity"] <= 1e-9:
            position["quantity"] = 0.0
            position["cost"] = 0.0

    holdings = []
    for symbol in sorted(positions):
        position = positions[symbol]
        if position["quantity"] == 0:
            continue
        holdings.append(Holding(
            symbol=symbol,
            isin=position["isin"],
            exchange=position["exchange"],
            quantity=position["quantity"],
            invested_amount=position["cost"],
            average_price=position["cost"] / position["quantity"],
        ))
    return holdings


def _transaction_fields(transaction, row_number):
    names = (
        "id", "trade_date", "symbol", "isin", "exchange", "transaction_type",
        "quantity", "price", "brokerage", "taxes", "net_amount", "created_at",
    )
    if hasattr(transaction, "keys"):
        return transaction
    if len(transaction) < 10:
        raise ValueError(f"Transaction {row_number}: expected at least 10 fields")
    return dict(zip(names, transaction))


def _number(value, field, row_number):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Transaction {row_number}: {field} must be a number"
        ) from None
    if not isfinite(number):
        raise ValueError(f"Transaction {row_number}: {field} must be finite")
    return number