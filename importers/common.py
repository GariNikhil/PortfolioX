"""Shared helpers for the importer modules.

Every importer returns the same ImportResult shape, raises ImportFileError
for file-level problems, and normalizes dates and numbers the same way, so
the UI can treat all import paths uniformly.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from calculations.fno import normalize_fno_symbol
from database import manager

try:
    import openpyxl
except ImportError:  # pragma: no cover - only hit without the openpyxl extra
    openpyxl = None

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y")

CURRENCY_MARKS = (",", "₹", "Rs", "rs", "INR")


class ImportFileError(Exception):
    """Raised when a file cannot be parsed as the expected import format."""


@dataclass(frozen=True)
class RowFailure:
    """One rejected data row, with its 1-based file row number and reason."""

    row_number: int
    reason: str


@dataclass
class ImportResult:
    """Summary of one import attempt (the report the UI will show)."""

    filename: str
    imported: int = 0
    duplicates: int = 0
    failures: list = field(default_factory=list)

    def summary(self):
        return (
            f"{self.filename}: {self.imported} imported, "
            f"{self.duplicates} duplicates, {len(self.failures)} failed rows"
        )


def normalize_date(value):
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


def parse_number(value, field_name, positive=False):
    """Parse a number cell that may carry currency or thousands marks."""

    text = str(value if value is not None else "").strip()
    for mark in CURRENCY_MARKS:
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


def is_blank_row(row):
    """Report whether a raw row carries no data at all."""

    return not any(str(cell).strip() if cell is not None else "" for cell in row)


def clean_symbol(value):
    """Strip a symbol/instrument cell, collapsing runs of internal whitespace."""

    return re.sub(r"\s+", " ", str(value or "").strip())


def canonical_trade_symbol(symbol):
    """Canonical identity of a symbol for duplicate detection.

    F&O text is first brought to one canonical shape (calculations.fno),
    then the symbol_aliases table maps verbatim equity variants — the same
    normalization rebuild_holdings() applies. So the same trade imported
    under different names ('VEDANTA' vs 'VEDANTA LIMITED', or two F&O
    expiry spellings) produces one key and a re-import skips it.
    """

    text = str(symbol or "").strip()
    normalized = normalize_fno_symbol(text)
    if normalized is not None:
        return normalized
    return manager.canonical_symbol(text.upper())


def trade_key(row):
    """Identity of a trade for re-import detection.

    Built from (date, canonical symbol, side, quantity, gross price in
    paise). Note: two genuinely identical same-day trades at the same
    price share a key, so a re-import treats the second one as a
    duplicate. This is the documented trade-off of content-key idempotency.
    """

    return (
        row["trade_date"],
        canonical_trade_symbol(row["symbol"]),
        row["transaction_type"],
        round(float(row["quantity"]), 4),
        round(float(row["price"] or 0) * 100),
    )


def existing_trade_keys():
    """Content keys of every transaction already stored (for duplicate skips)."""

    return {trade_key(row) for row in manager.get_transactions()}


def record_import(filename, source_kind, status):
    """Write the attempt to the imports audit table (never raises)."""

    try:
        manager.add_import(filename, source_kind, status)
    except Exception:  # the audit trail must not mask the real error
        pass


def _split_oversells(pending):
    """Split pending rows into (insertable, oversell_rows) without touching the DB.

    calculate_holdings() refuses to rebuild when any SELL exceeds the
    position built so far (e.g. a contract note selling shares bought in an
    earlier period, or held in demat). One such row would otherwise fail the
    whole batch. Mirroring its ordering (trade date, then insertion order)
    and 1e-9 tolerance, rows that would oversell are rejected up-front so
    the rest of the file still imports; the position state after this
    simulation is exactly what rebuild_holdings() will see.

    Two refinements keep legitimate real-world notes importing:

    - Symbols are canonicalized (F&O shape, then aliases) before matching —
      the same normalization rebuild_holdings() applies — so a note selling
      'PUNJAB NATIONAL BANK' is covered by a holding stored as 'PNB'.
    - Within a (symbol, date) group whose sells are covered by the day's
      buys plus the position held before the import (a same-day roundtrip,
      possibly listed sell-first in the note), buys are ordered before
      sells so the rebuild never sees a sell ahead of its same-day buy.
      Groups that remain infeasible keep their file order and the
      simulation rejects the rows that genuinely oversell.
    """

    positions = {
        str(holding["symbol"]).upper(): float(holding["quantity"])
        for holding in manager.get_holdings()
    }

    # Canonical symbol per row for position matching; rows keep their
    # verbatim symbol in the database.
    canonical = {id(row): canonical_trade_symbol(row["symbol"]) for row in pending}

    # Per (canonical symbol, date) groups, in first-appearance order.
    groups = {}
    for order, row in enumerate(pending):
        key = (canonical[id(row)], row["trade_date"])
        group = groups.setdefault(key, {"bought": 0.0, "sold": 0.0, "rows": []})
        quantity = float(row["quantity"])
        if row["transaction_type"] == "BUY":
            group["bought"] += quantity
        else:
            group["sold"] += quantity
        group["rows"].append((order, row))

    # Insert order: file order, except feasible groups go buys-first.
    ordered = []
    for key, group in groups.items():
        members = group["rows"]
        covered = (
            group["sold"] <= positions.get(key[0], 0.0) + group["bought"] + 1e-9
        )
        if covered and group["sold"]:
            members = (
                [item for item in members if item[1]["transaction_type"] == "BUY"]
                + [item for item in members if item[1]["transaction_type"] != "BUY"]
            )
        ordered.extend(members)

    # Simulate exactly what rebuild_holdings() will see: (trade date, id),
    # where id follows the insert order above.
    oversell_rows = set()
    oversell_reports = []
    for _index, (_order, row) in sorted(
        enumerate(ordered),
        key=lambda item: (item[1][1]["trade_date"], item[0]),
    ):
        symbol = canonical[id(row)]
        held = positions.get(symbol, 0.0)
        quantity = float(row["quantity"])

        if row["transaction_type"] == "SELL" and quantity > held + 1e-9:
            oversell_rows.add(id(row))
            oversell_reports.append((row, held))
            continue

        if row["transaction_type"] == "BUY":
            positions[symbol] = held + quantity
        else:
            positions[symbol] = max(held - quantity, 0.0)

    insertable = [row for _order, row in ordered if id(row) not in oversell_rows]
    return insertable, oversell_reports


def commit_import(filename, source_kind, rows, failures, skip_duplicates=True,
                  account_id=None):
    """Shared import-commit flow: dedupe, drop oversells, insert atomically, audit-log.

    The caller has already parsed the file (so `rows` are manager-ready
    mappings and `failures` the row-level rejections) and handled the
    "no importable rows" case. Rows that would oversell current holdings —
    legitimate in real contract notes that sell shares bought elsewhere —
    are converted into row-level failures instead of failing the batch.
    account_id tags the whole batch with one account (None = Unassigned).
    Returns the ImportResult; raises ImportFileError only if the database
    rejects the batch.
    """

    result = ImportResult(filename=filename, failures=list(failures))

    pending = rows
    if skip_duplicates:
        existing = existing_trade_keys()
        pending = [row for row in rows if trade_key(row) not in existing]
        result.duplicates = len(rows) - len(pending)

    pending, oversells = _split_oversells(pending)
    for row, held in oversells:
        result.failures.append(RowFailure(
            row_number=0,
            reason=(
                f"cannot sell {row['quantity']:g} of {row['symbol']}: only "
                f"{held:g} held at that point (the earlier buys are not part "
                "of this import)"
            ),
        ))

    if not pending:
        record_import(filename, source_kind, "SUCCESS")
        return result

    try:
        manager.add_transactions(pending, account_id=account_id)
        manager.rebuild_holdings()
    except Exception as error:  # batch rejected: keep the audit log truthful
        record_import(filename, source_kind, f"FAILED ({error})")
        raise ImportFileError(f"database rejected the batch: {error}") from error

    result.imported = len(pending)
    record_import(filename, source_kind, "SUCCESS")
    return result


# ------------------------------------------------------- tabular reading #


def read_tabular_rows(source):
    """Dispatch by suffix: raw rows from an .xlsx/.xlsm or .csv file.

    Shared by every spreadsheet-shaped importer (holding reports, mutual
    fund statements, ...). Raises ImportFileError for unsupported
    extensions and unreadable files.
    """

    source = Path(source)
    suffix = source.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx(source)
    if suffix == ".csv":
        return _read_csv(source)
    raise ImportFileError(
        f"unsupported format '{suffix}' (expected .xlsx or .csv)"
    )


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

    import csv

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


# ------------------------------------------------- account detail labels #

# Label rows that carry account details in statement headers, e.g.
# ('Unique Client Code', '1234567890') in a Groww stocks holdings file,
# ('Mobile Number', ...) or ('PAN', ...) in a Groww MF statement, or a
# PAN line in a bank statement. Keys are lowercased labels with a
# trailing colon stripped; values are accounts-table detail fields.
ACCOUNT_DETAIL_LABELS = {
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
    """Scan label/value rows of a statement for account detail fields.

    Picks up things like ('Unique Client Code', '1234567890') or a PAN
    line from a statement header. Returns a dict keyed by account detail
    field names (holder_name, ucc, pan, phone, account_number), or an
    empty dict when the file is unreadable or carries no labels.
    """

    try:
        raw_rows = read_tabular_rows(Path(path))
    except ImportFileError:
        return {}

    details = {}
    for row in raw_rows:
        if len(row) < 2 or row[0] is None:
            continue
        label = str(row[0]).strip().lower().rstrip(":")
        value = str(row[1]).strip() if row[1] is not None else ""
        field_name = ACCOUNT_DETAIL_LABELS.get(label)
        if field_name and value and field_name not in details:
            details[field_name] = value
    return details


def detect_account(path):
    """Identify which account a statement belongs to, from its details.

    Extracts account details from the file, then matches them against
    the stored accounts: UCC first (broker-specific), then PAN, then
    account number. Returns the matching account row, or None when the
    file carries no details or nothing matches.
    """

    details = extract_account_details(path)
    if not details:
        return None

    for field_name in ("ucc", "pan", "account_number"):
        value = details.get(field_name)
        if not value:
            continue
        for account in manager.get_accounts():
            stored = (account[field_name] or "").strip()
            if stored and stored.upper() == value.upper():
                return account

    return None
