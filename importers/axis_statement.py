"""Axis Bank statement import (PDF).

Parses Axis savings-account statements (the "Statement of Axis Account
No ..." layout) from extracted PDF text and stores every transaction as
a signed bank_transactions row.

Text-format notes (from the real statement in
referance/stock/bank accounts&statements):

- The header carries the customer details (name, Customer ID, IFSC,
  masked mobile, PAN) and "Statement of Axis Account No :<15 digits>
  for the period (From : ... To : ...)".
- The table is chronological: Tran Date / Chq No / Particulars / Debit /
  Credit / Balance / Init.Br. Particulars wrap across lines, and the
  numeric tail (one amount, the running balance, the branch code) may
  sit on the date line, on the last particulars line, or on its own
  line - so rows are assembled by token scanning, not line-by-line.
- Extracted text does NOT preserve which column (Debit or Credit) an
  amount came from. The running balance resolves it: with the opening
  balance given, balance(after) - balance(before) equals +amount for a
  credit and -amount for a debit. Every row is therefore self-verifying;
  a row whose arithmetic does not reconcile is reported as a failure
  instead of being guessed.
- "TRANSACTION TOTAL" gives the statement's own debit and credit sums;
  the parsed rows are checked against them, and "CLOSING BALANCE"
  against the last row's balance.
"""

import re
from pathlib import Path

from importers.bank_common import clean_description, import_bank_statement, read_pdf_pages
from importers.common import ImportFileError, RowFailure, normalize_date, record_import

SOURCE_KIND = "AXIS_STATEMENT"
BANK_NAME = "Axis Bank"

# A transaction starts on a line beginning with its Tran Date. The rest
# of the row (particulars, amounts) continues on the same and following
# lines.
_DATE_LINE = re.compile(r"^(?P<date>\d{2}-\d{2}-\d{4})\b\s*(?P<rest>.*)$")

# Rupee amounts as they appear in the numeric columns (no rupee mark,
# optional thousands commas, always two decimals) - either plain digits
# ('10305.56') or comma-grouped ('15,085.74').
_DECIMAL = re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}$")
# The Init.Br column: a short branch code, no decimals.
_BRANCH = re.compile(r"^\d{1,4}$")

_ACCOUNT_RE = re.compile(r"Account No\s*:?\s*(\d{5,})")
_PAN_RE = re.compile(r"PAN\s*:?\s*([A-Z]{5}\d{4}[A-Z])")
_NAME_RE = re.compile(r"^[A-Z][A-Z .&'-]{2,}$")


def import_axis_statement(path, account_id=None):
    """Import one Axis Bank statement PDF and return an ImportResult.

    account_id: a specific account chosen by the user wins; None means
    auto-detect from the statement's details and, when nothing matches,
    auto-create the 'Axis Bank' PERSONAL account (first import). File
    problems raise ImportFileError after a FAILED audit entry.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures, meta = parse_axis_statement(source)
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


def parse_axis_statement(path):
    """Read and parse one Axis statement PDF.

    Returns (rows, failures, meta): rows are manager-ready mappings
    {txn_date, description, amount, balance} in signed rupee floats;
    meta carries {"details", "opening_balance", "closing_balance"}.
    """

    pages = read_pdf_pages(path, SOURCE_KIND)
    return parse_axis_pages(pages)


def parse_axis_pages(pages):
    """Parse Axis statement page texts (pure; tests feed fixtures)."""

    lines = []
    for page in pages:
        lines.extend(page.splitlines())

    opening = None       # int paise
    closing = None
    total_debits = None  # int paise, from TRANSACTION TOTAL
    total_credits = None
    totals_line = None
    expect_totals = 0

    txns = []            # (line_no, date_text, particulars_tokens, amounts, balance)
    failures = []

    current_date = None
    current_line = None
    current_tokens = []

    def close_current():
        """Seal the open transaction when its numeric tail is complete."""

        nonlocal current_date, current_tokens
        tail = _extract_tail(current_tokens)
        if tail is None:
            return False
        amounts, balance, tail_size = tail
        particulars = current_tokens[:-tail_size]
        txns.append((current_line, current_date, particulars, amounts, balance))
        current_date = None
        current_tokens = []
        return True

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("OPENING BALANCE"):
            opening = _last_decimal(line)
            continue
        if line.startswith("CLOSING BALANCE"):
            closing = _last_decimal(line)
            continue
        if line.startswith("TRANSACTION TOTAL"):
            totals_line = line_number
            values = [
                token for token in line.split()[2:] if _DECIMAL.fullmatch(token)
            ]
            for value in values:
                if total_debits is None:
                    total_debits = _cents(value)
                else:
                    total_credits = _cents(value)
            expect_totals = 2 - len(values)
            continue
        if expect_totals:
            values = [token for token in line.split() if _DECIMAL.fullmatch(token)]
            if values:
                if total_debits is None:
                    total_debits = _cents(values[0])
                else:
                    total_credits = _cents(values[0])
                expect_totals -= 1
            continue

        match = _DATE_LINE.match(line)
        if match:
            if current_date is not None:
                failures.append(RowFailure(
                    row_number=current_line,
                    reason=(f"transaction dated {current_date} never got an "
                            "amount/balance (unterminated row)"),
                ))
            current_date = match.group("date")
            current_line = line_number
            current_tokens = match.group("rest").split()
            close_current()
            continue

        if current_date is None:
            continue  # header, legends, footer text

        current_tokens.extend(line.split())
        close_current()

    if current_date is not None:
        failures.append(RowFailure(
            row_number=current_line,
            reason=(f"transaction dated {current_date} never got an "
                    "amount/balance (unterminated row)"),
        ))

    if opening is None:
        raise ImportFileError(
            "could not find the OPENING BALANCE line - not an Axis "
            "account statement?"
        )

    rows, resolved_failures = _resolve_sides(txns, opening, failures)
    failures = resolved_failures

    _validate_totals(rows, total_debits, total_credits, totals_line, closing,
                     failures)

    details = _extract_details("\n".join(lines))
    meta = {
        "details": details,
        "opening_balance": opening / 100,
        "closing_balance": (closing / 100) if closing is not None else None,
    }
    return rows, failures, meta


def _extract_tail(tokens):
    """Pop (amounts, balance, token_count) off the right, or None.

    The tail is: [amount ...] balance branch, reading right to left.
    Bracketed numbers inside particulars (e.g. 'Int on SB AC [27.00]
    Tax[6.00]') never match because '] Tax[' breaks the decimal pattern.
    """

    if len(tokens) < 3:
        return None
    if not _BRANCH.fullmatch(tokens[-1]):
        return None
    if not _DECIMAL.fullmatch(tokens[-2]):
        return None

    amounts = []
    index = len(tokens) - 3
    while index >= 0 and _DECIMAL.fullmatch(tokens[index]):
        amounts.append(tokens[index])
        index -= 1
    amounts.reverse()
    tail_size = len(amounts) + 2
    return amounts, tokens[-2], tail_size


def _resolve_sides(txns, opening, failures):
    """Turn raw transactions into signed rows via the running balance.

    One amount: +delta means credit, -delta means debit. Two amounts:
    Debit then Credit column order, validated arithmetically. A row
    that does not reconcile is reported and skipped; the chain then
    continues from the statement's own balance so one bad row does not
    poison the rest.
    """

    rows = []
    previous = opening
    for line_number, date_text, part_tokens, amounts, balance_text in txns:
        balance = _cents(balance_text)
        delta = balance - previous

        debit = credit = None
        if len(amounts) == 1:
            amount = _cents(amounts[0])
            if amount == delta and amount != 0:
                credit, debit = amount, 0
            elif amount == -delta:
                debit, credit = amount, 0
        elif len(amounts) == 2:
            candidate_debit = _cents(amounts[0])
            candidate_credit = _cents(amounts[1])
            if previous - candidate_debit + candidate_credit == balance:
                debit, credit = candidate_debit, candidate_credit

        if debit is None:
            failures.append(RowFailure(
                row_number=line_number,
                reason=(
                    f"{date_text}: amount(s) {' '.join(amounts)} do not "
                    f"reconcile with the running balance "
                    f"({_rupees(previous)} -> {_rupees(balance)})"
                ),
            ))
            previous = balance
            continue

        description = clean_description(" ".join(part_tokens))
        rows.append({
            "txn_date": normalize_date(date_text),
            "description": description,
            "amount": (credit - debit) / 100,
            "balance": balance / 100,
        })
        previous = balance

    return rows, failures


def _validate_totals(rows, total_debits, total_credits, totals_line,
                     closing, failures):
    """Check the parsed rows against the statement's own totals."""

    if total_debits is not None or total_credits is not None:
        parsed_debits = sum(-row["amount"] for row in rows
                            if row["amount"] < 0)
        parsed_credits = sum(row["amount"] for row in rows
                             if row["amount"] > 0)
        if total_debits is not None and \
                abs(parsed_debits - total_debits / 100) > 0.005:
            failures.append(RowFailure(
                row_number=totals_line or 0,
                reason=(
                    f"TRANSACTION TOTAL debits {_rupees(total_debits)} but "
                    f"parsed rows sum to {parsed_debits:.2f}"
                ),
            ))
        if total_credits is not None and \
                abs(parsed_credits - total_credits / 100) > 0.005:
            failures.append(RowFailure(
                row_number=totals_line or 0,
                reason=(
                    f"TRANSACTION TOTAL credits {_rupees(total_credits)} but "
                    f"parsed rows sum to {parsed_credits:.2f}"
                ),
            ))

    if closing is not None and rows:
        last_balance = _cents(f"{rows[-1]['balance']:.2f}")
        if last_balance != closing:
            failures.append(RowFailure(
                row_number=totals_line or 0,
                reason=(
                    f"CLOSING BALANCE {_rupees(closing)} but the last row's "
                    f"balance is {_rupees(last_balance)}"
                ),
            ))


def _extract_details(full_text):
    """Account details from the statement header (name, a/c no, PAN)."""

    details = {}
    account = _ACCOUNT_RE.search(full_text)
    if account:
        details["account_number"] = account.group(1)
    pan = _PAN_RE.search(full_text)
    if pan:
        details["pan"] = pan.group(1)

    for line in full_text.splitlines():
        candidate = line.strip()
        if candidate and _NAME_RE.fullmatch(candidate):
            details["holder_name"] = candidate.title()
            break
    return details


def _last_decimal(line):
    """The last rupee amount on a line (e.g. the OPENING BALANCE value)."""

    for token in reversed(line.split()):
        if _DECIMAL.fullmatch(token):
            return _cents(token)
    return None


def _cents(text):
    """'1,234.56' -> 123456 (int paise)."""

    return int(round(float(text.replace(",", "")) * 100))


def _rupees(cents):
    """Paise back to a display string for failure messages."""

    return f"{cents / 100:,.2f}"
