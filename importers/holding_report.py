"""Broker holding-report import (Excel / CSV snapshot).

A holding report (Demat/holdings statement export) lists the CURRENT
position per symbol: quantity and average price. Unlike trade files it
is a snapshot, not a history, so rows do not become transactions — they
are stored as source='holding_report' rows in manual_holdings and
REPLACE the transaction-derived position at rebuild time (the report
knows about sells the contract notes may not).

Import semantics:

- The report is assigned to one account; a re-import for that account
  first deletes the account's previous holding_report rows, so symbols
  sold since the last report disappear instead of lingering.
- Re-importing is therefore idempotent per account: the latest report
  wins, which is exactly the "avg price as per latest data" rule.
- No sample file existed when the parser was first written, so column
  detection is keyword-based over common broker header names; it has
  since been validated against a real Groww stocks holdings export.

Header detection: a row qualifies when a symbol-ish, a quantity-ish and
an average-price-ish column are all found. Extra columns (ISIN, P/L,
...) are ignored; blank rows are skipped; bad data rows are
reported per row instead of aborting the import.

Extras: a closing-price column (if present) seeds the prices table
with source='holding_report' so market value lights up, and label/value
rows in the header (UCC, PAN, phone, account number) auto-fill the
account's detail fields without overwriting anything the user typed.
"""

from pathlib import Path

from importers.common import (
    ImportFileError,
    ImportResult,
    RowFailure,
    clean_symbol,
    extract_account_details,
    finish_import,
    is_blank_row,
    parse_number,
    read_tabular_rows,
    record_import,
)
from database import manager

SOURCE_KIND = "HOLDING_REPORT"

# Column detection, in priority order: the first header cell matching an
# earlier pattern wins, so 'buy avg' beats a bare 'price' and 'free qty'
# beats a generic 'balance'. Patterns are lowercase fragments matched
# against the normalized header cell.
_COLUMN_PATTERNS = {
    "symbol": (
        "symbol", "scrip", "instrument", "security", "stock name",
        "company name", "company", "stock",
    ),
    "quantity": (
        "free qty", "free quantity", "available qty", "deliverable qty",
        "qty", "quantity", "units", "balance",
    ),
    "average_price": (
        "buy avg", "buy price", "avg cost", "average cost",
        "average price", "avg price", "avg. price", "purchase price",
        "average", "avg",
    ),
}

# Optional columns: when the report also carries a market/closing price
# we store it in the prices table so market value and P&L light up
# immediately. Matched WITHOUT the exclusion list below, since those
# fragments are exactly what a closing-price column is called.
_OPTIONAL_COLUMN_PATTERNS = {
    "closing_price": (
        "closing price", "close price", "last traded price", "ltp",
        "market price", "current price", "cmp", "close",
    ),
}

# A row qualifies as the header when at least these canonical columns appear.
_HEADER_MATCH = ("symbol", "quantity", "average_price")


def import_holding_report(path, account_id=None):
    """Import a holding-report file and return an ImportResult.

    The report must be assigned to an existing account (a holdings
    statement is per broker account by nature). File-level problems raise
    ImportFileError after recording a FAILED audit entry; row-level
    problems never abort the import.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures = parse_holding_report(source)
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    if not rows:
        message = f"{filename} contains no importable holding rows"
        record_import(filename, SOURCE_KIND, f"FAILED ({message})")
        raise ImportFileError(message)

    # Auto-fill account details from label/value rows in the file
    # (e.g. 'Unique Client Code', '1234567890'). Only fills account
    # fields the user has not filled themselves.
    details = extract_account_details(source)
    if details and account_id is not None:
        try:
            manager.fill_account_details_if_empty(account_id, **details)
        except Exception:  # auto-fill must never block the import
            pass

    result_failures = list(failures)
    import_id = None
    try:
        # Audit first so the snapshot rows can carry the audit row's id;
        # the status flips to SUCCESS/FAILED once the batch is committed.
        import_id = record_import(filename, SOURCE_KIND, "PENDING")
        imported = manager.replace_holding_report(
            rows, account_id, import_id=import_id,
        )
        # Seed market prices from the report's closing-price column when
        # present, BEFORE the rebuild so market value and P&L light up.
        for row in rows:
            price = row.get("closing_price")
            if price is not None:
                manager.set_price(row["symbol"], price, source="holding_report")
        manager.rebuild_holdings()
    except Exception as error:
        finish_import(import_id, f"FAILED ({error})")
        raise ImportFileError(f"database rejected the batch: {error}") from error

    result = ImportResult(filename=filename, failures=result_failures)
    result.imported = imported
    finish_import(import_id, "SUCCESS")
    return result


def parse_holding_report(path):
    """Parse a holding-report file into (rows, failures).

    Rows are manager-ready mappings {symbol, quantity, average_price}
    with rupee floats; failures are RowFailure entries. Raises
    ImportFileError for unreadable files or a missing header.
    """

    source = Path(path)
    if not source.exists():
        raise ImportFileError(f"file not found: {source}")

    raw_rows = _read_rows(source)

    columns = _locate_header(raw_rows)
    if columns is None:
        raise ImportFileError(
            "could not find a header row with symbol, quantity and "
            "average price columns"
        )

    symbol_index = columns["symbol"]
    quantity_index = columns["quantity"]
    price_index = columns["average_price"]
    closing_index = columns.get("closing_price")

    rows, failures = [], []
    for row_number, raw in enumerate(raw_rows, start=1):
        if row_number <= columns["header_row"]:
            continue
        if is_blank_row(raw):
            continue

        symbol = clean_symbol(_cell(raw, symbol_index))
        if not symbol:
            failures.append(RowFailure(
                row_number=row_number, reason="missing symbol",
            ))
            continue
        try:
            quantity = parse_number(
                _cell(raw, quantity_index), "quantity", positive=True,
            )
            average_price = parse_number(
                _cell(raw, price_index), "average price",
            )
        except ValueError as error:
            failures.append(RowFailure(row_number=row_number, reason=str(error)))
            continue

        entry = {
            "symbol": symbol,
            "quantity": quantity,
            "average_price": average_price,
        }

        # The closing price is auxiliary: a bad value never fails the
        # holding row, it only skips the price seeding. A None cell is
        # simply empty, not the string "None".
        closing_cell = _cell(raw, closing_index) if closing_index is not None else None
        if closing_cell is not None and str(closing_cell).strip():
            try:
                entry["closing_price"] = parse_number(
                    closing_cell, "closing price",
                )
            except ValueError:
                failures.append(RowFailure(
                    row_number=row_number,
                    reason=(
                        f"{symbol}: invalid closing price "
                        f"'{str(closing_cell).strip()}' "
                        "(holding imported without its price)"
                    ),
                ))

        rows.append(entry)

    return rows, failures


def _cell(raw, index):
    """Cell at index, or '' when the row is shorter (ragged CSV lines)."""

    return raw[index] if index < len(raw) else ""


# Header fragments that disqualify a cell from column matching: a
# holdings report may carry sell-side averages and market-price columns
# alongside the buy average; neither is the cost basis.
_COLUMN_EXCLUSIONS = (
    "sell", "ltp", "last traded", "market price", "current price",
    "closing price", "cmp",
)


def _locate_header(raw_rows):
    """Find the header row and map canonical columns to cell indexes.

    Returns {"header_row": int, "symbol": i, "quantity": i,
    "average_price": i[, "closing_price": i]} or None when no row
    qualifies. The closing-price column is optional.
    """

    for row_number, raw in enumerate(raw_rows, start=1):
        normalized = [
            str(cell).strip().lower() if cell is not None else ""
            for cell in raw
        ]
        columns = {}
        for canonical, patterns in _COLUMN_PATTERNS.items():
            for index, cell in enumerate(normalized):
                if not cell or any(mark in cell for mark in _COLUMN_EXCLUSIONS):
                    continue
                if any(cell == pattern or pattern in cell for pattern in patterns):
                    columns[canonical] = index
                    break

        if all(name in columns for name in _HEADER_MATCH):
            for canonical, patterns in _OPTIONAL_COLUMN_PATTERNS.items():
                for index, cell in enumerate(normalized):
                    if not cell:
                        continue
                    if any(cell == pattern or pattern in cell for pattern in patterns):
                        columns[canonical] = index
                        break
            columns["header_row"] = row_number
            return columns

    return None


# Shared implementations live in importers.common so the mutual-fund
# importer (and future statement importers) reuse them; the names stay
# importable from this module for backwards compatibility.
_read_rows = read_tabular_rows
