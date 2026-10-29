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
- No sample file existed when this parser was written, so column
  detection is keyword-based over common broker header names and should
  be validated against a real export.

Header detection: a row qualifies when a symbol-ish, a quantity-ish and
an average-price-ish column are all found. Extra columns (ISIN, P/L,
LTP, ...) are ignored; blank rows are skipped; bad data rows are
reported per row instead of aborting the import.
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

    result_failures = list(failures)
    try:
        imported = manager.replace_holding_report(rows, account_id)
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

    suffix = source.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        raw_rows = _read_xlsx(source)
    elif suffix == ".csv":
        raw_rows = _read_csv(source)
    else:
        raise ImportFileError(
            f"unsupported holding-report format '{suffix}' "
            "(expected .xlsx or .csv)"
        )

    columns = _locate_header(raw_rows)
    if columns is None:
        raise ImportFileError(
            "could not find a header row with symbol, quantity and "
            "average price columns"
        )

    symbol_index = columns["symbol"]
    quantity_index = columns["quantity"]
    price_index = columns["average_price"]

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

        rows.append({
            "symbol": symbol,
            "quantity": quantity,
            "average_price": average_price,
        })

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
    "average_price": i} or None when no row qualifies.
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
            columns["header_row"] = row_number
            return columns

    return None


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
