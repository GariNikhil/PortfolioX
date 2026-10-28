"""Stocksledger "Portfolio" sheet import (Phase 3, hand-entered snapshot).

Parses the Portfolio sheet of a stocksledger template workbook (one row per
hand-entered holding: name, purchase price, qty, purchase date, brokerage)
and inserts each holding as a BUY transaction through database.manager with
the same guarantees as the other importers: exact INTEGER paise money,
ISO-8601 dates, atomic commit, content-key duplicate skipping, and an audit
entry in the imports table.

Format notes (from inspecting the real file in referance/stock/):

- This is a SNAPSHOT, not a trade history: only current holdings exist, so
  every row imports as a BUY and there is no sell side. Holdings opened and
  fully closed before the snapshot date cannot be reconstructed from it.
- The sheet repeats its header row (the template copies a block for each
  page) and some copies of the holding rows themselves; identical
  (symbol, date, qty, price) rows inside one file are imported once.
- Brokerage in this sheet is a rupee amount (a percentage of the
  investment filled in by the template), stored as-is.
- Decorative/derived columns (Gainers, Losers, Target, P/L, BEP, ...) are
  ignored; blank filler and instruction rows are skipped.
"""

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
    trade_key,
)

try:
    import openpyxl
except ImportError:  # pragma: no cover - only hit without the openpyxl extra
    openpyxl = None

COLUMN_ALIASES = {
    "name": "name",
    "purchase price": "price",
    "qty": "quantity",
    "pur dt": "purchase_date",
    "brokerage": "brokerage",
}

# A row qualifies as the header when at least these canonical columns appear.
HEADER_MATCH_ALIASES = ("name", "price", "quantity")

SOURCE_KIND = "STOCKSLEDGER_PORTFOLIO"


def import_stocksledger_portfolio(path, skip_duplicates=True):
    """Import a stocksledger Portfolio sheet and return an ImportResult.

    File-level problems (missing file, wrong sheet, no data rows) raise
    ImportFileError after recording a FAILED entry in the imports table.
    Row-level problems never abort the import: good rows persist and bad
    rows are listed on the result.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures = parse_stocksledger_portfolio(source)
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    if not rows:
        message = f"{filename} contains no importable holding rows"
        record_import(filename, SOURCE_KIND, f"FAILED ({message})")
        raise ImportFileError(message)

    return commit_import(filename, SOURCE_KIND, rows, failures, skip_duplicates)


def parse_stocksledger_portfolio(path):
    """Parse the Portfolio sheet into (valid_rows, failures) without the DB."""

    source = Path(path)
    if not source.is_file():
        raise ImportFileError(f"file not found: {source}")

    if openpyxl is None:
        raise ImportFileError(
            "reading XLSX portfolios requires the openpyxl package "
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
                rows = [row for row in sheet.iter_rows(values_only=True)]
                header_index = _locate_header(rows)
                if header_index is None:
                    continue
                return _parse_rows(rows, header_index)
    finally:
        workbook.close()  # release the file handle (Windows locks open files)

    raise ImportFileError(
        f"no sheet in {source.name} looks like a stocksledger Portfolio "
        "(expected columns: Name, Purchase Price, Qty, Pur Dt)"
    )


def _normalize_cell(value):
    return str(value).strip().lower() if value is not None else ""


def _locate_header(rows):
    """Find the Portfolio header row; prefer a sheet-level match anywhere."""

    for index, row in enumerate(rows):
        columns = _columns_for(row)
        if columns is None:
            continue
        if all(alias in columns for alias in HEADER_MATCH_ALIASES):
            return index
    return None


def _columns_for(row):
    """Map canonical column names to indexes; None if too few aliases match."""

    columns = {}
    for index, cell in enumerate(row):
        canonical = COLUMN_ALIASES.get(_normalize_cell(cell))
        if canonical is not None and canonical not in columns:
            columns[canonical] = index
    if len(columns) < len(HEADER_MATCH_ALIASES):
        return None
    return columns


def _cell(row, columns, name):
    index = columns.get(name)
    if index is None or index >= len(row):
        return None
    return row[index]


def _parse_rows(rows, header_index):
    """Validate holding rows; good rows become manager-ready dicts, bad rows fail.

    Identical holdings repeated inside the file (the template duplicates
    its block) are imported once: later copies are dropped in-file before
    the DB-level duplicate check ever sees them.
    """

    columns = _columns_for(rows[header_index])
    valid, failures = [], []
    seen = set()

    for offset, row in enumerate(rows[header_index + 1:]):
        row_number = header_index + offset + 2  # 1-based sheet row
        if is_blank_row(row):
            continue
        if _normalize_cell(_cell(row, columns, "name")) == "name":
            continue  # repeated header row

        raw_name = _cell(row, columns, "name")
        if raw_name is None or not str(raw_name).strip():
            continue  # template filler rows carry no stock name

        try:
            parsed = _parse_row(row, columns)
        except ValueError as error:
            failures.append(RowFailure(row_number=row_number, reason=str(error)))
            continue

        key = trade_key(parsed)
        if key in seen:
            continue  # in-file copy of the same holding
        seen.add(key)
        valid.append(parsed)

    return valid, failures


def _parse_row(row, columns):
    """Normalize one holding row into a BUY transaction."""

    symbol = clean_symbol(_cell(row, columns, "name"))
    quantity = parse_number(_cell(row, columns, "quantity"), "quantity",
                            positive=True)
    price = parse_number(_cell(row, columns, "price"), "purchase price",
                         positive=True)

    raw_date = _cell(row, columns, "purchase_date")
    if raw_date is None or not str(raw_date).strip():
        raise ValueError(f"missing purchase date for '{symbol}'")
    trade_date = normalize_date(raw_date)

    brokerage = 0.0
    raw_brokerage = _cell(row, columns, "brokerage")
    if raw_brokerage is not None and str(raw_brokerage).strip():
        brokerage = parse_number(raw_brokerage, "brokerage", positive=False)

    return {
        "trade_date": trade_date,
        "symbol": symbol.upper(),
        "isin": None,
        "exchange": None,
        "transaction_type": "BUY",  # snapshot import: no sell history exists
        "quantity": quantity,
        "price": price,
        "brokerage": brokerage,
        "taxes": 0.0,
    }