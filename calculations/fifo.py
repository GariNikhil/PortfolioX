"""FIFO realized profit and loss for BUY / SELL transactions.

This is an accounting calculation: each SELL is matched against the
oldest available BUY lots, and the result is the profit or loss that
matching produces. It performs no tax classification and writes nothing
to the database.

Rows may be database tuples in the `transactions` table's column order or
mappings with the same field names (money in rupees, as
`manager.get_transactions` returns it). Rows are processed by trade date,
then by id, so the caller's ordering never changes the result.

Matching key: ISIN when the row has one, otherwise the normalized symbol
plus exchange. The account is deliberately not part of the key, so a
position held in two accounts is treated as one pool.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from math import isfinite

# `SELECT *` order for the transactions table. Only the fields above
# `net_amount` are read, so a shorter tuple (the older tests' 12-field
# form) still maps correctly.
_COLUMNS = (
    "id", "trade_date", "symbol", "isin", "exchange", "transaction_type",
    "quantity", "price", "brokerage", "taxes", "net_amount", "account_id",
    "import_id", "created_at",
)

# Quantities are floats; treat dust from partial-lot division as zero
# instead of raising an oversell error on a rounding artefact.
_EPSILON = 1e-9


@dataclass(frozen=True)
class LotMatch:
    """One buy lot's share of a sale."""

    buy_id: int | None
    quantity: float
    cost: float
    proceeds: float
    realized_pnl: float


@dataclass(frozen=True)
class RealizedSale:
    """A sell and the buy lots it consumed."""

    sale_id: int | None
    trade_date: str
    symbol: str
    isin: str | None
    exchange: str | None
    quantity: float
    proceeds: float
    cost: float
    realized_pnl: float
    matches: tuple[LotMatch, ...]


@dataclass
class _Lot:
    """A remaining piece of a buy, in the order it should be consumed."""

    buy_id: int | None
    quantity: float
    cost: float


def calculate_fifo_realized(transactions):
    """Return one `RealizedSale` per sell, in chronological order.

    Buy charges (brokerage + taxes) are added to the lot's cost and travel
    with it, so a partially consumed lot keeps the same unit cost. Sell
    charges reduce that sale's net proceeds, which are then split across
    the matched lots in proportion to the quantity taken from each.

    Invalid rows and sells that exceed the available lots raise
    `ValueError`; an oversell is never treated as a short position.
    """

    rows = [
        _fields(row, row_number)
        for row_number, row in enumerate(transactions, start=1)
    ]
    ordered = sorted(rows, key=_sort_key)

    lots_by_key = defaultdict(deque)
    sales = []

    for row_number, trade in enumerate(ordered, start=1):
        symbol = _symbol(trade, row_number)
        transaction_type = _transaction_type(trade, row_number)
        quantity = _positive(trade["quantity"], "quantity", row_number)
        price = _amount(trade["price"], "price", row_number)
        brokerage = _amount(trade["brokerage"] or 0, "brokerage", row_number)
        taxes = _amount(trade["taxes"] or 0, "taxes", row_number)

        isin = _text(trade["isin"])
        exchange = _text(trade["exchange"])
        lots = lots_by_key[_instrument_key(isin, symbol, exchange)]

        if transaction_type == "BUY":
            lots.append(_Lot(
                buy_id=trade["id"],
                quantity=quantity,
                cost=quantity * price + brokerage + taxes,
            ))
            continue

        held = sum(lot.quantity for lot in lots)
        if quantity > held + _EPSILON:
            raise ValueError(
                f"Transaction {row_number}: cannot sell {quantity:g} shares "
                f"of {symbol}; only {held:g} are held"
            )

        net_proceeds = quantity * price - brokerage - taxes
        consumed = _consume(lots, quantity)
        matches = tuple(
            LotMatch(
                buy_id=buy_id,
                quantity=taken,
                cost=cost,
                proceeds=net_proceeds * (taken / quantity),
                realized_pnl=net_proceeds * (taken / quantity) - cost,
            )
            for buy_id, taken, cost in consumed
        )

        total_cost = sum(match.cost for match in matches)
        sales.append(RealizedSale(
            sale_id=trade["id"],
            trade_date=trade["trade_date"],
            symbol=symbol,
            isin=isin,
            exchange=exchange,
            quantity=quantity,
            proceeds=net_proceeds,
            cost=total_cost,
            realized_pnl=net_proceeds - total_cost,
            matches=matches,
        ))

    return sales


def _consume(lots, quantity):
    """Pop `quantity` off the oldest lots; return (buy_id, taken, cost)."""

    remaining = quantity
    consumed = []
    while remaining > _EPSILON:
        lot = lots[0]
        taken = min(lot.quantity, remaining)
        unit_cost = lot.cost / lot.quantity
        cost = unit_cost * taken
        lot.quantity -= taken
        lot.cost -= cost
        if lot.quantity <= _EPSILON:
            lots.popleft()
        remaining -= taken
        consumed.append((lot.buy_id, taken, cost))
    return consumed


def _sort_key(trade):
    """Trade date first, id as the tie-breaker; rows without an id go first."""

    identifier = trade["id"]
    if not isinstance(identifier, int):
        identifier = 0
    return (trade["trade_date"], identifier)


def _fields(transaction, row_number):
    """Normalize a tuple row or a mapping to the fields we read."""

    if hasattr(transaction, "keys"):
        return {
            "id": transaction.get("id"),
            "trade_date": _trade_date(transaction.get("trade_date"), row_number),
            "symbol": transaction.get("symbol"),
            "isin": transaction.get("isin"),
            "exchange": transaction.get("exchange"),
            "transaction_type": transaction.get("transaction_type"),
            "quantity": transaction.get("quantity"),
            "price": transaction.get("price"),
            "brokerage": transaction.get("brokerage"),
            "taxes": transaction.get("taxes"),
        }
    if len(transaction) < 10:
        raise ValueError(f"Transaction {row_number}: expected at least 10 fields")
    values = dict(zip(_COLUMNS, transaction))
    values["trade_date"] = _trade_date(values["trade_date"], row_number)
    return values


def _trade_date(value, row_number):
    """Trade dates must be non-empty strings so sorting is meaningful."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Transaction {row_number}: trade_date is required")
    return value


def _symbol(trade, row_number):
    value = trade["symbol"]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Transaction {row_number}: symbol is required")
    return value.strip().upper()


def _transaction_type(trade, row_number):
    value = str(trade["transaction_type"] or "").strip().upper()
    if value not in {"BUY", "SELL"}:
        raise ValueError(
            f"Transaction {row_number}: unsupported transaction type "
            f"{value!r}; expected BUY or SELL"
        )
    return value


def _instrument_key(isin, symbol, exchange):
    if isin:
        return ("isin", isin)
    return ("symbol", symbol, exchange or "")


def _text(value):
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value or None


def _positive(value, field, row_number):
    number = _number(value, field, row_number)
    if number <= 0:
        raise ValueError(f"Transaction {row_number}: {field} must be positive")
    return number


def _amount(value, field, row_number):
    number = _number(value, field, row_number)
    if number < 0:
        raise ValueError(
            f"Transaction {row_number}: {field} cannot be negative"
        )
    return number


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
