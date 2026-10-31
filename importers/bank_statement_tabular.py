"""Bank statement import from spreadsheets (XLSX / CSV).

The PDF statement importers (Axis, PNB mPassbook) parse fixed bank
layouts token by token. Banks also export statements as spreadsheets -
Axis netbanking offers Excel downloads, PNB internet banking exports
XLS - and those are plain tables, so this importer is generic: it
locates the header row by keyword (date / narration / debit / credit /
balance) and reads every data row, the way the holding-report importer
does for broker files.

Rows become signed bank_transactions rows (credit positive, debit
negative) through the shared bank-statement flow: account resolution
(explicit choice, then account-number auto-detection, then auto-creating
the bank's PERSONAL account), detail auto-fill, duplicate skipping, and
the account balance set to the statement's closing balance.
"""

import re
from pathlib import Path

from importers.bank_common import (
    clean_description,
    import_bank_statement,
)
from importers.common import (
    ImportFileError,
    RowFailure,
    extract_account_details,
    is_blank_row,
    normalize_date,
    parse_number,
    read_tabular_rows,
    record_import,
)
from database import manager

SOURCE_KIND = "BANK_STATEMENT"

# Account numbers hide in preamble text rows ("Statement of Axis Account
# No : 912345678901234"), not in label/value column pairs, so they are
# scanned out of every cell. Detection matches ONLY the account number
# (never PAN) - see bank_common.detect_bank_account.
_ACCOUNT_NUMBER_RE = re.compile(
    r"(?:account\s*(?:no|number)|a/c\s*no)\s*:?\s*(\d{5,})", re.IGNORECASE,
)

# Column detection, in priority order: the first header cell matching an
# earlier pattern wins. Patterns are lowercase fragments matched against
# the normalized header cell; short ambiguous tokens ('dr', 'cr') are
# deliberately absent because they substring-match too much.
_COLUMN_PATTERNS = {
    "date": (
        "tran date", "txn date", "transaction date", "value date",
        "posting date", "date",
    ),
    "description": (
        "narration", "particulars", "description", "remarks", "details",
    ),
    "debit": ("withdrawal", "withdrawl", "withdrawn", "debit"),
    "credit": ("deposit", "credit"),
    "balance": ("balance",),
}

# A row qualifies as the header when a date, a description and at least
# one amount column (debit or credit) are all found.
_HEADER_MATCH = ("date", "description")


def import_bank_statement_tabular(path, account_id=None, bank_name="Bank"):
    """Import one spreadsheet bank statement and return an ImportResult.

    account_id: a specific account chosen by the user wins; None means
    auto-detect from the statement's details and, when nothing matches,
    auto-create a PERSONAL account named after bank_name (first import).
    A file that carries no account number cannot be auto-detected on a
    re-import, so an existing PERSONAL account named after the bank is
    reused in that case (the first import created it). File problems
    raise ImportFileError after a FAILED audit entry.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures, meta = parse_bank_statement_tabular(source)
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    if account_id is None and not (meta["details"] or {}).get("account_number"):
        existing = manager.find_account_by_name(bank_name)
        if existing is not None and existing["kind"] == "PERSONAL":
            account_id = existing["id"]

    return import_bank_statement(
        filename=filename,
        source_kind=SOURCE_KIND,
        rows=rows,
        failures=failures,
        details=meta["details"],
        closing_balance=meta["closing_balance"],
        account_id=account_id,
        bank_name=bank_name,
    )


def parse_bank_statement_tabular(path):
    """Parse one spreadsheet bank statement.

    Returns (rows, failures, meta): rows are manager-ready mappings
    {txn_date, description, amount, balance} in signed rupee floats
    (credit positive, debit negative; balance None when the file has no
    balance column); meta carries {"details", "closing_balance"}.
    Raises ImportFileError for unreadable files or a missing header.
    """

    raw_rows = read_tabular_rows(path)

    columns = _locate_header(raw_rows)
    if columns is None:
        raise ImportFileError(
            "could not find a header row with date, description and "
            "debit/credit columns"
        )

    rows, failures = [], []
    last_balance = None
    for row_number, raw in enumerate(raw_rows, start=1):
        if row_number <= columns["header_row"]:
            continue
        if is_blank_row(raw):
            continue

        try:
            date_text = normalize_date(_cell(raw, columns["date"]))
        except ValueError:
            failures.append(RowFailure(
                row_number=row_number, reason="unreadable date",
            ))
            continue

        description = clean_description(_cell(raw, columns["description"]))
        if not description:
            failures.append(RowFailure(
                row_number=row_number, reason="missing description",
            ))
            continue

        try:
            debit = _amount(raw, columns.get("debit"))
            credit = _amount(raw, columns.get("credit"))
        except ValueError as error:
            failures.append(RowFailure(row_number=row_number, reason=str(error)))
            continue

        amount = credit - debit
        if amount == 0:
            failures.append(RowFailure(
                row_number=row_number,
                reason="row has no debit or credit amount",
            ))
            continue

        balance = None
        if columns.get("balance") is not None:
            balance_text = _cell(raw, columns["balance"])
            if balance_text:
                try:
                    balance = parse_number(balance_text, "balance")
                except ValueError:
                    balance = None  # a stray footer value; not fatal
            if balance is not None:
                last_balance = balance

        rows.append({
            "txn_date": date_text,
            "description": description,
            "amount": amount,
            "balance": balance,
        })

    details = _extract_details_safely(path)
    return rows, failures, {
        "details": details,
        "closing_balance": last_balance,
    }


def _locate_header(raw_rows):
    """The (columns, header_row) of the first usable header row, or None."""

    for row_number, row in enumerate(raw_rows, start=1):
        found = {}
        for index, cell in enumerate(row):
            text = str(cell or "").strip().lower()
            if not text:
                continue
            for name, patterns in _COLUMN_PATTERNS.items():
                if name in found:
                    continue
                if any(pattern in text for pattern in patterns):
                    found[name] = index
                    break
        if all(name in found for name in _HEADER_MATCH) and (
            "debit" in found or "credit" in found
        ):
            found["header_row"] = row_number
            return found
    return None


def _cell(row, index):
    """The row's cell text at index, or '' when the row is short."""

    if index is None or index >= len(row):
        return ""
    return str(row[index] if row[index] is not None else "").strip()


def _amount(row, index):
    """Parsed amount at index; 0 for a missing column or blank cell."""

    if index is None:
        return 0.0
    text = _cell(row, index)
    if not text:
        return 0.0
    return parse_number(text, "amount")


def _extract_details_safely(path):
    """Account details from label/value rows plus preamble text cells."""

    details = extract_account_details(path)
    if "account_number" not in details:
        number = _scan_account_number(path)
        if number:
            details["account_number"] = number
    return details


def _scan_account_number(path):
    """An account number from preamble text cells, or None."""

    try:
        raw_rows = read_tabular_rows(path)
    except ImportFileError:
        return None
    for row in raw_rows:
        for cell in row:
            match = _ACCOUNT_NUMBER_RE.search(str(cell or ""))
            if match:
                return match.group(1)
    return None
