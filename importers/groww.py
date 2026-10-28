"""Groww tradebook import (Phase 3).

Parses a Groww tradebook (CSV or XLSX), validates every row, and inserts the
accepted rows through database.manager so that money lands as exact INTEGER
paise, dates are ISO-8601, and the batch commits atomically. Re-importing the
same file skips already-imported transactions (content-key matching). Every
attempt is recorded in the imports table, including failed file reads.

The parser accepts a small family of column headers (see HEADER_ALIASES) and
date formats, so exports across Groww versions keep working. Files that are
not tradebooks — such as UPI expense exports or broker contract notes — are
rejected with a message naming the missing columns instead of importing junk.
"""

import csv
import math
import re
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from database import manager

try:
    import openpyxl
except ImportError:  # pragma: no cover - only hit without the openpyxl extra
    openpyxl = None

XLSX_SUFFIXES = {".xlsx", ".xlsm"}
CSV_SUFFIXES = {".csv", ".txt", ""}

REQUIRED_COLUMNS = ("date", "symbol", "quantity", "price", "side")

# Column recognition is by header text (case- and whitespace-insensitive).
HEADER_ALIASES = {
    "date": ("trade date", "date"),
    "symbol": ("symbol", "stock name", "script name", "instrument"),
    "quantity": ("quantity", "qty", "shares"),
    "price": ("price", "price/unit", "trade price", "price per unit"),
    "side": ("buy/sell", "type", "side", "action"),
}

OPTIONAL_ALIASES = {
    "isin": ("isin",),
    "exchange": ("exchange",),
    "brokerage": ("brokerage",),
    "taxes": ("taxes", "charges", "tax"),
    # Validated but not persisted: the v2 schema has no columns for them.
    "trade_type": ("trade type", "trade category"),
}

SIDE_ALIASES = {
    "buy": "BUY",
    "b": "BUY",
    "buy(b)": "BUY",
    "sell": "SELL",
    "s": "SELL",
    "sell(s)": "SELL",
}

VALID_TRADE_TYPES = {
    "intraday": "INTRADAY",
    "delivery": "DELIVERY",
}

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y")

SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9&._\-/ ]+$")
ISIN_PATTERN = re.compile(r"^[A-Za-z]{2}[A-Za-z0-9]{9}[0-9]$")


class GrowwImportError(Exception):
    """Raised when a file cannot be parsed as a Groww tradebook at all."""


@dataclass(frozen=True)
class RowFailure:
    """One rejected data row, with its 1-based file row number and reason."""

    row_number: int
    reason: str


@dataclass
class ImportResult:
    """Summary of one import attempt (the Phase 3 report the UI will show)."""

    filename: str
    imported: int = 0
    duplicates: int = 0
    failures: list = field(default_factory=list)

    def summary(self):
        return (
            f"{self.filename}: {self.imported} imported, "
            f"{self.duplicates} duplicates, {len(self.failures)} failed rows"
        )


def import_groww_tradebook(path, skip_duplicates=True):
    """Import a tradebook file and return an ImportResult.

    File-level problems (missing file, wrong columns, no data rows) raise
    GrowwImportError after recording a FAILED entry in the imports table.
    Row-level problems never abort the import: good rows persist and bad
    rows are listed on the result.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures = parse_groww_tradebook(source)
    except GrowwImportError as error:
        _record_import(filename, f"FAILED ({error})")
        raise

    if not rows:
        message = f"FAILED (no importable data rows in {filename})"
        _record_import(filename, message)
        raise GrowwImportError(f"{filename} contains no importable data rows")

    result = ImportResult(filename=filename, failures=failures)

    pending = rows
    if skip_duplicates:
        existing = _existing_trade_keys()
        pending = []
        for row in rows:
            if _trade_key(row) in existing:
                result.duplicates += 1
            else:
                pending.append(row)

    try:
        manager.add_transactions(pending)
        manager.rebuild_holdings()
    except Exception as error:  # batch rejected: keep the audit log truthful
        _record_import(filename, f"FAILED ({error})")
        raise GrowwImportError(f"database rejected the batch: {error}") from error

    result.imported = len(pending)
    _record_import(filename, "SUCCESS")
    return result


def parse_groww_tradebook(path):
    """Parse a tradebook file into (valid_rows, failures) without touching the DB.

    Valid rows are mappings ready for database.manager.add_transactions:
    trade_date (ISO text), symbol, isin, exchange, transaction_type (BUY/SELL),
    quantity, price (rupees), brokerage, taxes.
    """

    source = Path(path)
    if not source.is_file():
        raise GrowwImportError(f"file not found: {source}")

    suffix = source.suffix.lower()
    if suffix in XLSX_SUFFIXES:
        data_rows, header_index, columns = _read_xlsx(source)
    elif suffix in CSV_SUFFIXES:
        data_rows, header_index, columns = _read_csv(source)
    else:
        raise GrowwImportError(
            f"unsupported file type '{suffix}'; save the tradebook as CSV or XLSX"
        )

    if not data_rows:
        raise GrowwImportError(f"{source.name} has a tradebook header but no data rows")

    return _parse_rows(data_rows, start_row_number=header_index + 2, columns=columns)


def _read_csv(source):
    """Read CSV rows, find the header row, return (data_rows, header_index, columns)."""

    try:
        with open(source, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise GrowwImportError(f"could not read {source.name} as CSV: {error}") from error
    return _locate_header(rows)


def _read_xlsx(source):
    """Read XLSX rows the same way, scanning sheets until a tradebook header matches."""

    if openpyxl is None:
        raise GrowwImportError(
            "reading XLSX files requires the openpyxl package "
            "(pip install -r requirements.txt)"
        )

    try:
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    except Exception as error:
        raise GrowwImportError(f"could not open {source.name} as XLSX: {error}") from error

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
                try:
                    return _locate_header(rows)
                except GrowwImportError:
                    continue  # not this sheet; try the next one
    finally:
        workbook.close()  # release the file handle (Windows locks open files)

    raise GrowwImportError(
        f"no sheet in {source.name} has the columns of a Groww tradebook "
        f"(required: {', '.join(REQUIRED_COLUMNS)})"
    )


def _locate_header(rows):
    """Find the header row and build a column-name -> index map.

    A row is a candidate header when it matches at least two required column
    aliases; that makes rejection messages name the missing columns (for
    example, an UPI expense export has a Date column but no Symbol).
    """

    for index, row in enumerate(rows):
        columns = _map_columns(row)
        if columns is None:
            continue

        missing = [name for name in REQUIRED_COLUMNS if name not in columns]
        if missing:
            found = ", ".join(str(cell) for cell in row if cell not in (None, ""))
            raise GrowwImportError(
                f"not a Groww tradebook: missing required column(s) "
                f"{', '.join(missing)}; header found: {found or '(empty)'}"
            )
        return rows[index + 1 :], index, columns

    raise GrowwImportError(
        "no header row found with the columns of a Groww tradebook "
        f"(required: {', '.join(REQUIRED_COLUMNS)})"
    )


def _normalize_header(cell):
    return re.sub(r"\s+", " ", str(cell)).strip().lower() if cell is not None else ""


def _map_columns(row):
    """Map canonical column names to indexes using aliases.

    Returns None when the row does not look like a tradebook header (fewer
    than two required aliases match). Alias order resolves ambiguity: the
    first matching alias wins.
    """

    normalized = [_normalize_header(cell) for cell in row]

    def find(aliases):
        for alias in aliases:
            if alias in normalized:
                return normalized.index(alias)
        return None

    matched = {}
    for name, aliases in HEADER_ALIASES.items():
        index = find(aliases)
        if index is not None:
            matched[name] = index

    if len(matched) < 2:
        return None

    columns = dict(matched)
    for name, aliases in OPTIONAL_ALIASES.items():
        index = find(aliases)
        if index is not None:
            columns[name] = index

    return columns


def _parse_rows(data_rows, start_row_number, columns):
    """Validate data rows; good rows become manager-ready dicts, bad rows fail."""

    valid, failures = [], []
    for offset, row in enumerate(data_rows):
        row_number = start_row_number + offset
        if _is_blank(row):
            continue

        try:
            valid.append(_parse_row(row, row_number, columns))
        except ValueError as error:
            failures.append(RowFailure(row_number=row_number, reason=str(error)))

    return valid, failures


def _cell(row, columns, name):
    index = columns.get(name)
    if index is None or index >= len(row):
        return None
    return row[index]


def _is_blank(row):
    return not any(
        str(cell).strip() if cell is not None else "" for cell in row
    )


def _parse_row(row, row_number, columns):
    """Normalize one row or raise ValueError with a user-facing reason."""

    raw_date = _cell(row, columns, "date")
    trade_date = _normalize_date(raw_date)

    raw_symbol = _cell(row, columns, "symbol")
    symbol = str(raw_symbol or "").strip()
    if not symbol:
        raise ValueError("missing symbol")
    if not SYMBOL_PATTERN.match(symbol):
        raise ValueError(f"invalid symbol '{symbol}'")

    quantity = _parse_number(_cell(row, columns, "quantity"), "quantity", positive=True)
    price = _parse_number(_cell(row, columns, "price"), "price", positive=True)

    raw_side = _cell(row, columns, "side")
    side = SIDE_ALIASES.get(str(raw_side or "").strip().lower())
    if side is None:
        raise ValueError(f"invalid buy/sell value '{raw_side}' (expected Buy or Sell)")

    raw_trade_type = _cell(row, columns, "trade_type")
    if raw_trade_type is not None and str(raw_trade_type).strip():
        if str(raw_trade_type).strip().lower() not in VALID_TRADE_TYPES:
            raise ValueError(
                f"invalid trade type '{raw_trade_type}' (expected Intraday or Delivery)"
            )

    brokerage = 0.0
    raw_brokerage = _cell(row, columns, "brokerage")
    if raw_brokerage is not None and str(raw_brokerage).strip():
        brokerage = _parse_number(raw_brokerage, "brokerage", positive=False)

    taxes = 0.0
    raw_taxes = _cell(row, columns, "taxes")
    if raw_taxes is not None and str(raw_taxes).strip():
        taxes = _parse_number(raw_taxes, "taxes", positive=False)

    isin = None
    raw_isin = _cell(row, columns, "isin")
    if raw_isin is not None and str(raw_isin).strip():
        isin = str(raw_isin).strip().upper()
        if not ISIN_PATTERN.match(isin):
            raise ValueError(f"invalid ISIN '{raw_isin}'")

    exchange = None
    raw_exchange = _cell(row, columns, "exchange")
    if raw_exchange is not None and str(raw_exchange).strip():
        exchange = str(raw_exchange).strip().upper()

    return {
        "trade_date": trade_date,
        "symbol": symbol.upper(),
        "isin": isin,
        "exchange": exchange,
        "transaction_type": side,
        "quantity": quantity,
        "price": price,
        "brokerage": brokerage,
        "taxes": taxes,
    }


def _normalize_date(value):
    """Accept display dates and normalize to ISO-8601 YYYY-MM-DD text."""

    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(
        f"invalid date '{text}' (supported: YYYY-MM-DD, DD-MM-YYYY, "
        "DD/MM/YYYY, DD Mon YYYY)"
    )


def _parse_number(value, field_name, positive):
    """Parse a rupee/quantity cell that may carry currency or thousands marks."""

    text = str(value if value is not None else "").strip()
    for mark in (",", "₹", "Rs", "rs", "INR"):
        text = text.replace(mark, "")
    text = text.strip()

    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"invalid {field_name} '{value}' (expected a number)") from None

    if not math.isfinite(number):
        raise ValueError(f"invalid {field_name} '{value}' (not a finite number)")

    if positive and number <= 0:
        raise ValueError(f"invalid {field_name} '{value}' (must be a positive number)")
    if not positive and number < 0:
        raise ValueError(f"invalid {field_name} '{value}' (cannot be negative)")

    return number


def _existing_trade_keys():
    """Content keys of every transaction already stored (for duplicate skips)."""

    keys = set()
    for row in manager.get_transactions():
        keys.add(_trade_key(row))
    return keys


def _trade_key(row):
    """Identity of a trade for re-import detection.

    Built from (date, symbol, side, quantity, gross price in paise). Note:
    two genuinely identical same-day trades at the same price share a key,
    so a re-import treats the second one as a duplicate. This is the
    documented trade-off of content-key idempotency.
    """

    return (
        row["trade_date"],
        str(row["symbol"]).upper(),
        row["transaction_type"],
        round(float(row["quantity"]), 4),
        _to_paise_key(row["price"]),
    )


def _to_paise_key(rupee_price):
    return round(float(rupee_price or 0) * 100)


def _record_import(filename, status):
    """Write the attempt to the imports audit table (never raises)."""

    try:
        manager.add_import(filename, "GROWW_TRADEBOOK", status)
    except Exception:  # the audit trail must not mask the real error
        pass
