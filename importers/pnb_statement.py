"""PNB ONE mPassbook statement import (PDF, password-protected).

Parses Punjab National Bank mPassbook statements ("Generated through
PNB ONE") and stores every transaction as a signed bank_transactions
row.

Text-format notes (from the real statement in
referance/stock/bank accounts&statements):

- The file is encrypted; the password is the PNB account number itself.
  It comes from the secure vault (kind 'PNB_MPASSBOOK'); a file without
  a stored password raises PasswordRequiredError so the UI prompts once.
- Header: Branch / Customer details, then "Statement of
  Account:<number> For Period: DD/MM/YYYY to DD/MM/YYYY".
- Table columns: Date / Instrument ID / Amount / Type / Balance /
  Remarks. Rows are NEWEST FIRST (reverse chronological). Remarks wrap
  across lines mid-token, so continuation lines are concatenated without
  a separator to keep UPI ids intact.
- Unlike the Axis statement, DR/CR is explicit, so no balance arithmetic
  is needed to sign the rows - but the running balance is still checked
  (after re-ordering chronologically) and a broken chain is reported as
  a failure row instead of passing silently.
- The last page's disclaimer text sits between table rows; footer lines
  (***... / bullet markers) switch footer mode on until the next real
  row so they never pollute a remark.
"""

import re
from pathlib import Path

from importers.bank_common import clean_description, import_bank_statement, read_pdf_pages
from importers.common import ImportFileError, RowFailure, normalize_date, record_import

SOURCE_KIND = "PNB_MPASSBOOK"
BANK_NAME = "PNB Bank"

_ROW = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amount>\d[\d,]*\.\d{2})\s+"
    r"(?P<type>DR|CR)\s+"
    r"(?P<balance>\d[\d,]*\.\d{2})\s*"
    r"(?P<remarks>.*)$"
)

# Lines that start the end-of-statement disclaimer; once seen, non-row
# lines are no longer remark continuations (until the next row).
_FOOTER_MARKERS = ("***", "\u25cf")  # '***Generated through PNB ONE', bullets

_ACCOUNT_RE = re.compile(r"Statement of Account\s*:?\s*(\d{5,})")
_NAME_RE = re.compile(r"Customer Name:\s*(.+)")


def import_pnb_statement(path, account_id=None):
    """Import one PNB mPassbook statement PDF and return an ImportResult.

    account_id: a specific account chosen by the user wins; None means
    auto-detect from the statement's details and, when nothing matches,
    auto-create the 'PNB Bank' PERSONAL account (first import). An
    encrypted file without a stored password raises
    PasswordRequiredError (the once-only prompt).
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures, meta = parse_pnb_statement(source)
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    return import_bank_statement(
        filename=filename,
        source_kind=SOURCE_KIND,
        rows=rows,
        failures=failures,
        details=meta["details"],
        closing_balance=meta["closing_balance"],
        account_id=account_id,
        bank_name=BANK_NAME,
    )


def parse_pnb_statement(path):
    """Read (decrypting via the vault) and parse one PNB statement PDF."""

    pages = read_pdf_pages(path, SOURCE_KIND)
    return parse_pnb_pages(pages)


def parse_pnb_pages(pages):
    """Parse PNB mPassbook page texts (pure; tests feed fixtures)."""

    rows_raw = []        # (line_no, date_text, amount, type, balance, remarks)
    failures = []
    footer_mode = False
    current = None

    for page in pages:
        for line_number, raw_line in enumerate(page.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue

            match = _ROW.match(line)
            if match:
                current = {
                    "line": line_number,
                    "date": match.group("date"),
                    "amount": match.group("amount"),
                    "type": match.group("type"),
                    "balance": match.group("balance"),
                    "remarks": match.group("remarks").strip(),
                }
                rows_raw.append(current)
                footer_mode = False
                continue

            if current is None or footer_mode:
                continue  # header / disclaimer text
            if line.startswith(_FOOTER_MARKERS):
                footer_mode = True
                continue

            # Wrapped remark continuation (mid-token: join without space).
            current["remarks"] += line

    if not rows_raw:
        raise ImportFileError(
            "could not find any transaction rows - not a PNB mPassbook "
            "statement?"
        )

    rows, chain_failures = _validate_chain(rows_raw)
    failures.extend(chain_failures)

    full_text = "\n".join(pages)
    details = _extract_details(full_text)
    # The statement is newest-first, so the closing balance is the FIRST
    # row's balance.
    closing = _cents(rows_raw[0]["balance"]) / 100

    meta = {"details": details, "closing_balance": closing}
    return rows, failures, meta


def _validate_chain(rows_raw):
    """Re-order newest-first rows chronologically and check balances.

    Returns (rows, failures). The DR/CR type is explicit, so a broken
    balance chain never blocks the import - it is reported per row so a
    parsing bug or bank anomaly is visible.
    """

    ordered = list(reversed(rows_raw))
    rows = []
    chain_failures = []
    previous = None
    for entry in ordered:
        amount = _cents(entry["amount"])
        signed = amount if entry["type"] == "CR" else -amount
        balance = _cents(entry["balance"])

        if previous is not None and previous + signed != balance:
            chain_failures.append(RowFailure(
                row_number=entry["line"],
                reason=(
                    f"{entry['date']}: balance {balance / 100:,.2f} does not "
                    f"reconcile (previous {previous / 100:,.2f} "
                    f"{'+' if signed >= 0 else '-'} {amount / 100:,.2f})"
                ),
            ))
        previous = balance

        rows.append({
            "txn_date": normalize_date(entry["date"]),
            "description": clean_description(entry["remarks"]),
            "amount": signed / 100,
            "balance": balance / 100,
        })
    return rows, chain_failures


def _extract_details(full_text):
    """Account details from the statement header (name, a/c number)."""

    details = {}
    account = _ACCOUNT_RE.search(full_text)
    if account:
        details["account_number"] = account.group(1)
    name = _NAME_RE.search(full_text)
    if name:
        details["holder_name"] = name.group(1).strip().title()
    return details


def _cents(text):
    """'15,085.74' -> 1508574 (int paise)."""

    return int(round(float(text.replace(",", "")) * 100))
