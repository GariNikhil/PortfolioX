"""Contract-note "Orders" sheet import (Phase 3, real broker files).

Parses the Orders sheet of a broker contract-note workbook (one row per
executed trade, with Buy(B)/Sell(S), quantity, trade price and brokerage per
unit) and inserts the rows through database.manager with the same guarantees
as the Groww importer: exact INTEGER paise money, ISO-8601 dates, atomic
commit, content-key duplicate skipping, and an audit entry in the imports
table.

Format notes (from inspecting the real files in referance/stock/):

- The sheet has NO date column. These workbooks are multi-day
  concatenations (each day is a block starting with a repeated header row),
  so the caller must supply the single trade_date applied to every row.
  Importing a multi-day workbook therefore requires splitting it first.
- Instrument descriptions are stored verbatim (whitespace-collapsed), e.g.
  "BANKNIFTY 45500 CE 13 Jul 2023". They are NOT normalized into
  symbol/strike/expiry parts.
- Repeated header rows, per-instrument "Total" rows and block "Net Total"
  rows are skipped.
- "Buy(B)/Sell(S)" decides the side; when the cell is empty the quantity
  sign is used instead (the sheet stores sells as negative quantities).
- Only "Brokerage per Unit" is available on the sheet; brokerage is stored
  as per-unit x quantity and taxes as 0 (other levies are not itemized).
"""

import re
import warnings
from pathlib import Path

from importers.common import (
    ImportFileError,
    RowFailure,
    clean_symbol,
    commit_import,
    is_blank_row,
    normalize_date,
    parse_number,
    record_import,
)

try:
    import openpyxl
except ImportError:  # pragma: no cover - only hit without the openpyxl extra
    openpyxl = None

ORDERS_HEADER_ALIASES = (
    "order no.",
    "security/contract description",
    "buy(b)/ sell(s)",
    "quantity",
    "trade no.",
)
MIN_HEADER_MATCHES = 3

SOURCE_KIND = "CONTRACT_NOTE_ORDERS"


def import_contract_note(path, trade_date, skip_duplicates=True, account_id=None):
    """Import one contract-note Orders sheet for a single trade date.

    File-level problems (missing file, wrong sheet, no data rows) raise
    ImportFileError after recording a FAILED entry in the imports table.
    Row-level problems never abort the import: good rows persist and bad
    rows are listed on the result.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures = parse_contract_note(source, trade_date)
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    if not rows:
        message = f"{filename} contains no importable trade rows"
        record_import(filename, SOURCE_KIND, f"FAILED ({message})")
        raise ImportFileError(message)

    return commit_import(filename, SOURCE_KIND, rows, failures, skip_duplicates,
                         account_id)


def parse_contract_note(path, trade_date):
    """Parse an Orders sheet into (valid_rows, failures) without touching the DB.

    Valid rows are mappings ready for database.manager.add_transactions, all
    stamped with the caller-supplied trade_date.
    """

    iso_date = normalize_date(trade_date)

    source = Path(path)
    if not source.is_file():
        raise ImportFileError(f"file not found: {source}")

    if openpyxl is None:
        raise ImportFileError(
            "reading XLSX contract notes requires the openpyxl package "
            "(pip install -r requirements.txt)"
        )

    try:
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    except Exception as error:
        raise ImportFileError(
            f"could not open {source.name} as XLSX: {error}"
        ) from error

    try:
        # openpyxl warns about cosmetic Excel extensions it drops; harmless
        # for data extraction and only noise in a desktop UI.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=".*extension is not supported.*",
                category=UserWarning,
            )
            for sheet in workbook.worksheets:
                sheet_rows = [row for row in sheet.iter_rows(values_only=True)]
                header_index = _locate_orders_header(sheet_rows)
                if header_index is None:
                    continue
                return _parse_rows(
                    sheet_rows,
                    header_index=header_index,
                    trade_date=iso_date,
                )
    finally:
        workbook.close()  # release the file handle (Windows locks open files)

    raise ImportFileError(
        f"no sheet in {source.name} looks like a contract-note Orders sheet "
        "(expected columns: Order no., Security/Contract description, "
        "Buy(B)/Sell(S), Quantity)"
    )


def _normalize_cell(value):
    """Lowercase and collapse whitespace (headers wrap across lines in-cell)."""

    return re.sub(r"\s+", " ", str(value)).strip().lower() if value is not None else ""


def _locate_orders_header(rows):
    """Return the index of the first Orders-sheet header row, or None."""

    for index, row in enumerate(rows):
        normalized = [_normalize_cell(cell) for cell in row]
        matches = sum(alias in normalized for alias in ORDERS_HEADER_ALIASES)
        if matches >= MIN_HEADER_MATCHES:
            return index
    return None


def _parse_rows(rows, header_index, trade_date):
    """Validate data rows; good rows become manager-ready dicts, bad rows fail."""

    valid, failures = [], []
    for offset, row in enumerate(rows[header_index + 1:]):
        row_number = header_index + offset + 2  # 1-based sheet row
        if is_blank_row(row):
            continue
        if _is_repeated_header(row):
            continue
        if _is_total_row(row):
            continue

        try:
            parsed = _parse_row(row, trade_date)
        except ValueError as error:
            failures.append(RowFailure(row_number=row_number, reason=str(error)))
            continue
        if parsed is not None:
            valid.append(parsed)

    return valid, failures


def _is_repeated_header(row):
    """Report whether a row is one of the sheet's repeated header rows.

    Some header copies start with 'Order no.' while shifted variants carry
    'Column1' in the first cell and the wrapped 'Security/Contract
    description' label in the description column.
    """

    if _normalize_cell(row[0] if row else None) == "order no.":
        return True
    return _normalize_cell(row[4] if len(row) > 4 else None) == (
        "security/contract description"
    )


def _is_total_row(row):
    """Report whether a row is a per-instrument Total or block Net Total row."""

    for cell in row[:5]:
        text = _normalize_cell(cell)
        if text == "total" or "net total" in text:
            return True
    return False


def _cell(row, index):
    return row[index] if index < len(row) else None


def _parse_row(row, trade_date):
    """Normalize one row or raise ValueError with a user-facing reason.

    Returns None for rows that carry no trade (kept for clarity); blank,
    header and Total rows never reach here.
    """

    symbol = clean_symbol(_cell(row, 4))
    if not symbol:
        return None  # summary/remark rows without an instrument

    raw_qty = _cell(row, 7)
    qty_text = str(raw_qty if raw_qty is not None else "").strip()
    side_from_sign = None
    if qty_text.startswith("-"):
        side_from_sign = "SELL"
        qty_text = qty_text[1:]

    raw_side = str(_cell(row, 6) or "").strip().upper()
    if raw_side in ("B", "BUY"):
        side = "BUY"
    elif raw_side in ("S", "SELL"):
        side = "SELL"
    elif side_from_sign is not None:
        side = side_from_sign
    else:
        raise ValueError(f"missing Buy(B)/Sell(S) for '{symbol}'")

    quantity = parse_number(qty_text or None, "quantity", positive=True)
    # Zero price is legitimate for expired options (closed at 0); only
    # negative prices are invalid.
    price = parse_number(_cell(row, 8), "price", positive=False)

    brokerage = 0.0
    raw_brokerage = _cell(row, 9)
    if raw_brokerage is not None and str(raw_brokerage).strip():
        per_unit = parse_number(raw_brokerage, "brokerage", positive=False)
        brokerage = per_unit * quantity

    exchange = None
    raw_exchange = _cell(row, 5)
    if raw_exchange is not None and str(raw_exchange).strip():
        exchange = str(raw_exchange).strip().upper()

    return {
        "trade_date": trade_date,
        "symbol": symbol.upper(),
        "isin": None,
        "exchange": exchange,
        "transaction_type": side,
        "quantity": quantity,
        "price": price,
        "brokerage": brokerage,
        "taxes": 0.0,
    }