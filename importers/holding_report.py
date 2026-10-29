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

import csv
from pathlib import Path

from importers.common import (
    ImportFileError,
    ImportResult,
    RowFailure,
    clean_symbol,
    is_blank_row,
    parse_number,
    record_import,
)
from database import manager

try:
    import openpyxl
except ImportError:  # pragma: no cover - only hit without the openpyxl extra
    openpyxl = None

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
    try:
        imported = manager.replace_holding_report(rows, account_id)
        # Seed market prices from the report's closing-price column when
        # present, BEFORE the rebuild so market value and P&L light up.
        for row in rows:
            price = row.get("closing_price")
            if price is not None:
                manager.set_price(row["symbol"], price, source="holding_report")
        manager.rebuild_holdings()
    except Exception as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise ImportFileError(f"database rejected the batch: {error}") from error

    result = ImportResult(filename=filename, failures=result_failures)
    result.imported = imported
    record_import(filename, SOURCE_KIND, "SUCCESS")
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


def _read_rows(source):
    """Dispatch by suffix: raw rows from an .xlsx/.xlsm or .csv file."""

    suffix = source.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx(source)
    if suffix == ".csv":
        return _read_csv(source)
    raise ImportFileError(
        f"unsupported holding-report format '{suffix}' "
        "(expected .xlsx or .csv)"
    )


# Label rows that carry account details in statement headers, e.g.
# ('Unique Client Code', '1234567890') in a Groww stocks holdings file
# or a PAN line in a bank statement. Keys are lowercased labels with a
# trailing colon stripped; values are account detail field names.
_LABEL_MAP = {
    "name": "holder_name",
    "account holder": "holder_name",
    "holder name": "holder_name",
    "unique client code": "ucc",
    "ucc": "ucc",
    "client code": "ucc",
    "pan": "pan",
    "pan no": "pan",
    "pan number": "pan",
    "mobile": "phone",
    "mobile no": "phone",
    "mobile number": "phone",
    "phone": "phone",
    "phone number": "phone",
    "account number": "account_number",
    "account no": "account_number",
    "account no.": "account_number",
    "a/c no": "account_number",
    "a/c no.": "account_number",
    "a/c number": "account_number",
}


def extract_account_details(path):
    """Scan label/value rows of a report for account detail fields.

    Picks up things like ('Unique Client Code', '1234567890') or a PAN
    line from a statement header. Returns a dict keyed by account detail
    field names (ucc, pan, phone, account_number), or an empty dict when
    the file is unreadable or carries no recognizable labels.
    """

    try:
        raw_rows = _read_rows(Path(path))
    except ImportFileError:
        return {}

    details = {}
    for row in raw_rows:
        if len(row) < 2 or row[0] is None:
            continue
        label = str(row[0]).strip().lower().rstrip(":")
        value = str(row[1]).strip() if row[1] is not None else ""
        field = _LABEL_MAP.get(label)
        if field and value and field not in details:
            details[field] = value
    return details


def _read_xlsx(source):
    """All cell rows of the first worksheet, or an ImportFileError."""

    if openpyxl is None:
        raise ImportFileError("openpyxl is not installed - cannot read .xlsx")

    try:
        workbook = openpyxl.load_workbook(source, data_only=True, read_only=True)
    except Exception as error:
        raise ImportFileError(f"cannot open workbook: {error}") from error

    try:
        sheet = workbook.worksheets[0]
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _read_csv(source):
    """All rows of a CSV file, tolerating comma/semicolon/tab delimiters."""

    try:
        text = source.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as error:
        raise ImportFileError(f"cannot read file: {error}") from error

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel  # plain comma default

    return [row for row in csv.reader(text.splitlines(), dialect)]
