"""Contract-note PDF import (Phase 3, real broker archive files).

Parses broker contract-note PDFs — the same Orders layout as the xlsx
importer (`importers/contract_note.py`), but as extracted text — and inserts
the trades through database.manager with the shared guarantees (paise money,
ISO dates, atomic commit, duplicate skipping, audit trail).

Encrypted files: contract notes are usually password-protected. The
password comes from the secure vault (`security/vault.py`); if the vault has
no password for the file yet, PasswordRequiredError is raised so the UI (or
operator script) prompts exactly once, stores it, and retries. Every later
import of similarly protected files then runs without user interaction.

Text-format notes (from the real notes in referance/stock/CONTRACT NOTE):

- Each note carries its own "Trade date DD-MM-YYYY" header line, so the
  importer is self-dating (unlike the undated Orders xlsx).
- Trade rows start with a long order number, then order time, trade number,
  trade time, the Security/Contract description, the exchange token, the
  Buy(B)/Sell(S) flag, and the numeric tail: quantity (negative for sells),
  rate, optional brokerage/net-rate/closing-rate columns, and the Net Total
  last.
- The optional middle columns are ambiguous in extracted text, so brokerage
  is derived from money instead of column position: charges = |Net Total| −
  quantity×rate. This keeps the stored row exactly consistent with the
  note's own Net Total, and yields 0 for the common no-charges rows.
- Page headers, per-instrument Total rows and Net Total lines never match
  the trade-row pattern and are skipped.
- Instrument descriptions are stored verbatim (upper-cased,
  whitespace-collapsed), like every other importer.
"""

import re
from pathlib import Path

from importers.common import (
    ImportFileError,
    RowFailure,
    clean_symbol,
    commit_import,
    record_import,
)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - only hit without the pypdf extra
    PdfReader = None

from security import vault
from security.vault import PasswordRequiredError

SOURCE_KIND = "CONTRACT_NOTE_PDF"

_TRADE_LINE = re.compile(
    r"^(?P<order_no>\d{10,16})\s+"
    r"(?P<order_time>\d{1,2}:\d{2}:\d{2})\s+"
    r"(?P<trade_no>\d{3,12})\s+"
    r"(?P<trade_time>\d{1,2}:\d{2}:\d{2})\s+"
    r"(?P<rest>.+?)\s*$"
)

_TRADE_DATE = re.compile(r"Trade date\s+(\d{1,2}-\d{1,2}-\d{4})", re.IGNORECASE)

_NUMBER = re.compile(r"^-?[\d,]+(?:\.\d+)?$")


def import_contract_note_pdf(path, skip_duplicates=True, account_id=None):
    """Import one contract-note PDF and return an ImportResult.

    File-level problems (missing file, wrong content, no importable rows)
    raise ImportFileError after recording a FAILED audit entry. An encrypted
    note without a stored password raises PasswordRequiredError (the
    once-only prompt) without writing an audit entry, because the attempt
    is not a failure — it is waiting for the user.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures = parse_contract_note_pdf(source)
    except PasswordRequiredError:
        raise  # waiting for the user's one-time password, not a failure
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    if not rows:
        message = f"{filename} contains no importable trade rows"
        record_import(filename, SOURCE_KIND, f"FAILED ({message})")
        raise ImportFileError(message)

    return commit_import(filename, SOURCE_KIND, rows, failures, skip_duplicates,
                         account_id)


def parse_contract_note_pdf(path):
    """Read, decrypt if needed, and parse one contract-note PDF."""

    source = Path(path)
    if not source.is_file():
        raise ImportFileError(f"file not found: {source}")

    if PdfReader is None:
        raise ImportFileError(
            "reading PDF contract notes requires the pypdf package "
            "(pip install -r requirements.txt)"
        )

    try:
        reader = PdfReader(str(source))
    except Exception as error:
        raise ImportFileError(
            f"could not open {source.name} as PDF: {error}"
        ) from error

    if reader.is_encrypted:
        password = vault.password_for(source, SOURCE_KIND)
        if password is None:
            raise PasswordRequiredError(
                f"{source.name} is password-protected and no password is "
                f"stored for it yet (provide it once; it is remembered in "
                "the encrypted vault)"
            )
        try:
            decrypted = reader.decrypt(password)
        except Exception as error:
            raise PasswordRequiredError(
                f"the stored password was rejected for {source.name}: {error}"
            ) from error
        if decrypted is None or decrypted == 0:  # PasswordType.NOT_DECRYPTED
            raise PasswordRequiredError(
                f"the stored password was rejected for {source.name}"
            )

    pages = []
    try:
        for page in reader.pages:
            pages.append(page.extract_text() or "")
    except Exception as error:
        raise ImportFileError(
            f"could not extract text from {source.name}: {error}"
        ) from error

    text = "\n".join(pages)
    if not text.strip():
        raise ImportFileError(f"{source.name} contains no extractable text")

    return parse_contract_note_lines(text, filename=source.name)


def parse_contract_note_lines(text, filename="contract note"):
    """Parse extracted contract-note text into (valid_rows, failures).

    This core is file-free so tests can feed synthetic text.
    """

    date_match = _TRADE_DATE.search(text)
    if date_match is None:
        raise ImportFileError(
            f"{filename}: no 'Trade date DD-MM-YYYY' header found - the file "
            "does not look like a contract note"
        )
    trade_date = _iso_from_dmy(date_match.group(1))

    lines = text.splitlines()
    valid, failures = [], []
    merged_through = set()  # line numbers consumed as wrap continuations
    for line_number, line in enumerate(lines, start=1):
        if line_number in merged_through:
            continue
        match = _TRADE_LINE.match(line.strip())
        if match is None:
            continue  # page headers, Totals, Net Totals, page furniture

        if not _has_side_token(match.group("rest")):
            merged = _unwrap_wrapped_description(lines, line_number - 1)
            if merged is not None:
                match = _TRADE_LINE.match(merged)
                merged_through.update((line_number + 1, line_number + 2))

        try:
            valid.append(_parse_line(match.groupdict(), trade_date))
        except ValueError as error:
            failures.append(RowFailure(row_number=line_number, reason=str(error)))

    return valid, failures


_WRAP_YEAR = re.compile(r"^\d{4}$")
_WRAP_TAIL = re.compile(r"^[A-Za-z]+\s+[BS]\s+-?[\d,]+(?:\.\d+)?(?:\s|$)")


def _unwrap_wrapped_description(lines, index):
    """Join a wrapped F&O trade line back into one logical line, or None.

    pypdf wraps long Security/Contract descriptions across physical lines:
    '1600000000000000 12:29:07 521238859 12:29:07 BANKNIFTY 45700 CE 20 Jul'
    / '2023' / 'NSE B 25 138.20 138.20 -3455.00'. The continuation is
    recognized by a bare year on the next line and an exchange+side+numbers
    tail on the line after that.
    """

    if index + 2 >= len(lines):
        return None
    year = lines[index + 1].strip()
    tail = lines[index + 2].strip()
    if not _WRAP_YEAR.fullmatch(year) or not _WRAP_TAIL.match(tail):
        return None
    merged = f"{lines[index].strip()} {year} {tail}"
    return merged if _TRADE_LINE.match(merged) else None


def _iso_from_dmy(text):
    """DD-MM-YYYY display date -> ISO-8601 (zero-padded)."""

    day, month, year = text.split("-")
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _parse_line(fields, trade_date):
    """Normalize one trade line into a manager-ready transaction dict."""

    side, exchange, description, numbers = _split_tail(fields["rest"])

    # Sells arrive as negative quantities; the stored magnitude is positive
    # with the side carrying the direction (same as the xlsx importer).
    quantity = abs(_number(numbers[0], "quantity", signed=True))
    rate = _number(numbers[1], "price")
    if len(numbers) < 3:
        raise ValueError(
            f"trade line for '{description}' has no Net Total column"
        )
    net_total = _number(numbers[-1], "net total", signed=True)

    # Brokerage derived from money, not column position: the optional middle
    # columns (brokerage / net rate / closing rate) are ambiguous in text,
    # but |Net Total| - quantity*rate isolates the charges exactly.
    net_paise = round(abs(net_total) * 100)
    gross_paise = round(quantity * rate * 100)
    charges_paise = max(net_paise - gross_paise, 0)
    brokerage = charges_paise / 100

    return {
        "trade_date": trade_date,
        "symbol": clean_symbol(description).upper(),
        "isin": None,
        "exchange": exchange,
        "transaction_type": side,
        "quantity": quantity,
        "price": rate,
        "brokerage": brokerage,
        "taxes": 0.0,
    }


def _split_tail(rest):
    """Split the line tail into (side, exchange, description, numbers).

    The tail is '<description> <exchange> <B|S> <numbers...>'. The side is
    the B/S token followed by a number; everything before the exchange token
    is the verbatim description.
    """

    tokens = rest.split()
    side_index = _side_index(tokens)
    if side_index is None or side_index < 1:
        raise ValueError(f"no Buy(B)/Sell(S) flag found in '{rest}'")

    description = " ".join(tokens[: side_index - 1])
    if not description:
        raise ValueError(f"no Security/Contract description in '{rest}'")

    side = "BUY" if tokens[side_index] == "B" else "SELL"
    exchange = tokens[side_index - 1]
    numbers = [_strip_commas(token) for token in tokens[side_index + 1:]]

    if len(numbers) < 2:
        raise ValueError(f"trade line '{rest}' has too few numeric columns")

    return side, exchange.upper(), description, numbers


def _side_index(tokens):
    """Index of the B/S flag token followed by a number, or None."""

    for index, token in enumerate(tokens):
        if token in ("B", "S") and index + 1 < len(tokens) \
                and _NUMBER.match(tokens[index + 1]):
            return index
    return None


def _has_side_token(rest):
    """Whether a line tail already carries its exchange/side/numbers part."""

    return _side_index(rest.split()) is not None


def _strip_commas(token):
    return token.replace(",", "")


def _number(text, field_name, signed=False):
    """Parse one numeric token; raises ValueError with a usable reason."""

    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"invalid {field_name} '{text}' (expected a number)") from None
    if not signed and value < 0:
        raise ValueError(f"invalid {field_name} '{text}' (cannot be negative)")
    return value