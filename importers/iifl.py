"""IIFL Securities "Trade Listing" import (Phase 3, real broker files).

Parses the TradeListing_Equity_Currency sheet of an IIFL trade-listing .xls
(one row per instrument per trade date, with aggregated Buy and Sell sides)
and inserts the rows through database.manager with the same guarantees as
the other importers: exact INTEGER paise money, ISO-8601 dates, atomic
commit, content-key duplicate skipping, and an audit entry in the imports
table.

Format notes (from inspecting the real file in referance/stock/):

- Rows are dated (DD/MM/YYYY text) and span many days, unlike the undated
  contract-note Orders sheet.
- One sheet row can yield up to TWO transactions (BUY and SELL) because
  IIFL aggregates both sides into one instrument/day row.
- Equity rows (NSECASH) carry a plain ticker in Name (e.g. PENIND); the
  numeric Code (513228) is the exchange scrip id, not a symbol. F&O rows
  (NSEFNO, Option Type CE/PE) build the symbol as
  "<Code> <Strike> <OptionType> <expiry-ISO>".
- "Market Rate" is used as the trade price and "Brokerage" as the rupee
  brokerage; IIFL's per-unit "Net Rate" does not reconcile with
  Amt +/- Brokerage, so it is deliberately ignored (see
  docs/contract-note-import.md).
- Legacy .xls requires the xlrd package; xlrd cannot write .xls files, so
  tests cover the parser core with synthetic rows plus file-level error
  paths.
"""

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
    import xlrd
except ImportError:  # pragma: no cover - only hit without the xlrd extra
    xlrd = None

# A row qualifies as the header when at least these aliases all appear.
HEADER_MATCH_ALIASES = ("trade date", "buy qty", "sell qty")
MAX_HEADER_SCAN_ROWS = 15

COLUMN_ALIASES = {
    "exchange": "exchange",
    "trade date": "trade_date",
    "code": "code",
    "name": "name",
    "expiry date": "expiry",
    "strike price": "strike",
    "option type": "option_type",
    "buy qty": "buy_qty",
    "buy market rate": "buy_rate",
    "buy brokerage": "buy_brokerage",
    "sell qty": "sell_qty",
    "sell market rate": "sell_rate",
    "sell brokerage": "sell_brokerage",
}

SOURCE_KIND = "IIFL_TRADE_LISTING"


def import_iifl_trade_listing(path, skip_duplicates=True, account_id=None):
    """Import an IIFL Trade Listing .xls and return an ImportResult.

    File-level problems (missing file, wrong sheet, no data rows) raise
    ImportFileError after recording a FAILED entry in the imports table.
    Row-level problems never abort the import: good rows persist and bad
    rows are listed on the result.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures = parse_iifl_trade_listing(source)
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    if not rows:
        message = f"{filename} contains no importable trade rows"
        record_import(filename, SOURCE_KIND, f"FAILED ({message})")
        raise ImportFileError(message)

    return commit_import(filename, SOURCE_KIND, rows, failures, skip_duplicates,
                         account_id)


def parse_iifl_trade_listing(path):
    """Parse a Trade Listing .xls into (valid_rows, failures) without the DB."""

    source = Path(path)
    if not source.is_file():
        raise ImportFileError(f"file not found: {source}")

    if xlrd is None:
        raise ImportFileError(
            "reading .xls trade listings requires the xlrd package "
            "(pip install -r requirements.txt)"
        )

    try:
        book = xlrd.open_workbook(str(source))
    except Exception as error:
        raise ImportFileError(
            f"could not open {source.name} as XLS: {error}"
        ) from error

    datemode = book.datemode
    for sheet in book.sheets():
        rows = [sheet.row_values(r) for r in range(sheet.nrows)]
        header_index = _locate_header(rows)
        if header_index is None:
            continue
        return parse_trade_listing_rows(rows, header_index, datemode=datemode)

    raise ImportFileError(
        f"no sheet in {source.name} looks like an IIFL Trade Listing "
        "(expected columns: Trade Date, Buy Qty, Sell Qty)"
    )


def _normalize_cell(value):
    return str(value).strip().lower() if value is not None else ""


def _locate_header(rows):
    """Find the Trade Listing header row within the first MAX_HEADER_SCAN_ROWS."""

    for index, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        normalized = [_normalize_cell(cell) for cell in row]
        if all(alias in normalized for alias in HEADER_MATCH_ALIASES):
            return index
    return None


def _columns_for(header_row):
    """Map canonical column names to indexes from the header row."""

    columns = {}
    for index, cell in enumerate(header_row):
        canonical = COLUMN_ALIASES.get(_normalize_cell(cell))
        if canonical is not None and canonical not in columns:
            columns[canonical] = index
    return columns


def _cell(row, columns, name):
    index = columns.get(name)
    if index is None or index >= len(row):
        return None
    return row[index]


def _parse_date_cell(value, datemode):
    """Normalize an IIFL Trade Date cell (DD/MM/YYYY text or Excel float)."""

    if isinstance(value, float) and value > 0:
        if xlrd is None:  # pragma: no cover - guarded upstream
            raise ValueError("reading .xls dates requires the xlrd package")
        converted = xlrd.xldate.xldate_as_datetime(value, datemode)
        return converted.date().isoformat()
    return normalize_date(value)


def _parse_expiry_cell(value):
    """Normalize an Expiry Date cell (stored as a YYYYMMDD number)."""

    if value is None or str(value).strip() == "":
        return None
    digits = str(int(float(value))).zfill(8)
    return normalize_date(f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}")


def _format_strike(value):
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def parse_trade_listing_rows(rows, header_index, datemode=0):
    """Parse sheet rows below the header into (valid_rows, failures).

    This core is xlrd-free at the call site (date cells arrive either as
    DD/MM/YYYY text or Excel floats), so tests can feed synthetic lists
    without a real .xls file.
    """

    columns = _columns_for(rows[header_index])
    valid, failures = [], []

    for offset, row in enumerate(rows[header_index + 1:]):
        row_number = header_index + offset + 2  # 1-based sheet row
        if is_blank_row(row):
            continue

        try:
            valid.extend(_parse_row(row, columns, datemode))
        except ValueError as error:
            failures.append(RowFailure(row_number=row_number, reason=str(error)))

    return valid, failures


def _parse_row(row, columns, datemode):
    """Normalize one sheet row into 0..2 manager-ready transactions."""

    exchange = str(_cell(row, columns, "exchange") or "").strip().upper()
    trade_date = _parse_date_cell(_cell(row, columns, "trade_date"), datemode)

    code = str(_cell(row, columns, "code") or "").strip()
    name = clean_symbol(_cell(row, columns, "name"))
    option_type = str(_cell(row, columns, "option_type") or "").strip().upper()

    symbol = _build_symbol(code, name, option_type, columns, row)
    if not symbol:
        raise ValueError("missing instrument Name/Code")

    buy_qty = _side_quantity(row, columns, "buy_qty")
    sell_qty = _side_quantity(row, columns, "sell_qty")
    if not buy_qty and not sell_qty:
        raise ValueError(f"no buy or sell quantity for '{symbol}'")

    transactions = []
    if buy_qty:
        transactions.append(
            _transaction(
                trade_date, symbol, exchange, "BUY", buy_qty,
                row, columns, "buy_rate", "buy_brokerage",
            )
        )
    if sell_qty:
        transactions.append(
            _transaction(
                trade_date, symbol, exchange, "SELL", sell_qty,
                row, columns, "sell_rate", "sell_brokerage",
            )
        )
    return transactions


def _build_symbol(code, name, option_type, columns, row):
    """Equity rows use the ticker (Name); F&O rows build a composite symbol."""

    is_fno = option_type in ("CE", "PE") or "FNO" in _fno_exchange_hint(columns, row)
    if not is_fno:
        return name or code

    strike_cell = _cell(row, columns, "strike")
    if strike_cell is None or str(strike_cell).strip() == "":
        raise ValueError("missing Strike Price for F&O row")
    strike = _format_strike(strike_cell)

    expiry = _parse_expiry_cell(_cell(row, columns, "expiry"))
    expiry_text = expiry or "unknown-expiry"

    return f"{code} {strike} {option_type} {expiry_text}".upper()


def _fno_exchange_hint(columns, row):
    return str(_cell(row, columns, "exchange") or "").upper()


def _side_quantity(row, columns, column_name):
    """Parse a side quantity cell; returns None when the side was not traded."""

    raw = _cell(row, columns, column_name)
    text = str(raw if raw is not None else "").strip()
    if text == "":
        return None
    return parse_number(raw, column_name.replace("_", " "), positive=False)


def _transaction(trade_date, symbol, exchange, side, quantity, row, columns,
                 rate_column, brokerage_column):
    """Build one manager-ready transaction for one side of a sheet row."""

    rate = parse_number(_cell(row, columns, rate_column), f"{side} market rate",
                        positive=False)  # zero is legitimate (expired options)

    brokerage = 0.0
    raw_brokerage = _cell(row, columns, brokerage_column)
    if raw_brokerage is not None and str(raw_brokerage).strip():
        brokerage = parse_number(raw_brokerage, "brokerage", positive=False)

    return {
        "trade_date": trade_date,
        "symbol": symbol.upper(),
        "isin": None,
        "exchange": exchange or None,
        "transaction_type": side,
        "quantity": quantity,
        "price": rate,
        "brokerage": brokerage,
        "taxes": 0.0,
    }