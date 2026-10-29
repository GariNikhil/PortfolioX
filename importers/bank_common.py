"""Shared machinery for bank-statement importers (Axis, PNB, ...).

Bank statements are PDFs, so this module owns PDF reading (including the
once-only vault password flow for encrypted files) and the import flow
shared by every bank: resolve the target account (explicit choice, then
auto-detection from the statement's details, then auto-creating a
PERSONAL account for the bank), auto-fill its details, store the
transactions, and set the account balance to the statement's closing
balance.

Statement rows are signed: amount is positive for credits and negative
for debits, in rupees; balance is the running balance after the
transaction. Both are converted to INTEGER paise by the manager.
"""

from pathlib import Path

from importers.common import ImportFileError, ImportResult, record_import
from importers.common import detect_account_from_details
from database import manager

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - only hit without the pypdf extra
    PdfReader = None

from security import vault
from security.vault import PasswordRequiredError


def read_pdf_pages(path, password_kind):
    """Extracted text of every page, decrypting via the vault when needed.

    password_kind is the vault kind for this bank's files (e.g.
    'PNB_MPASSBOOK'). An encrypted file without a stored password raises
    PasswordRequiredError so the UI can prompt exactly once; a rejected
    stored password raises PasswordRequiredError too (the user may have
    typo'd it originally). Unreadable files raise ImportFileError.
    """

    source = Path(path)
    if not source.is_file():
        raise ImportFileError(f"file not found: {source}")

    if PdfReader is None:
        raise ImportFileError(
            "reading bank-statement PDFs requires the pypdf package "
            "(pip install -r requirements.txt)"
        )

    try:
        reader = PdfReader(str(source))
    except Exception as error:
        raise ImportFileError(
            f"could not open {source.name} as PDF: {error}"
        ) from error

    if reader.is_encrypted:
        password = vault.password_for(source, password_kind)
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
            f"could not read {source.name}: {error}"
        ) from error
    return pages


def import_bank_statement(*, filename, source_kind, rows, failures,
                          details, closing_balance, account_id, bank_name):
    """Shared import flow for one parsed bank statement.

    account_id resolution, in order: the explicit choice (a specific
    account picked in the UI), then auto-detection by matching the
    statement's details (account number / PAN) against stored accounts,
    then auto-creating a PERSONAL account named after the bank. The
    account's empty detail fields are filled from the statement, the
    transactions are stored with duplicate skipping, and the account
    balance is set to the statement's closing balance. Returns an
    ImportResult; file-level problems raise ImportFileError after a
    FAILED audit entry.
    """

    if not rows:
        message = f"{filename} contains no importable transactions"
        record_import(filename, source_kind, f"FAILED ({message})")
        raise ImportFileError(message)

    account = None
    created_note = None
    if account_id is not None:
        account = manager.find_account_by_id(account_id)
        if account is None:
            message = f"account id {account_id} does not exist"
            record_import(filename, source_kind, f"FAILED ({message})")
            raise ImportFileError(message)
    if account is None:
        account = detect_account_from_details(details)
    if account is None:
        # First import of this bank: create its account. Re-imports
        # detect it instead, via the account number filled below.
        new_id = manager.add_account(bank_name, "PERSONAL")
        account = manager.find_account_by_id(new_id)
        created_note = f"Created account '{bank_name}' (PERSONAL)"

    try:
        imported, duplicates = manager.add_bank_transactions(
            rows, account["id"],
        )
        if details:
            manager.fill_account_details_if_empty(account["id"], **details)
        if closing_balance is not None:
            manager.set_account_balance(account["id"], closing_balance)
    except Exception as error:
        record_import(filename, source_kind, f"FAILED ({error})")
        raise ImportFileError(f"database rejected the batch: {error}") from error

    result = ImportResult(filename=filename, failures=list(failures))
    result.imported = imported
    result.duplicates = duplicates
    result.notes.append(f"Account: {account['name']}")
    if created_note:
        result.notes.append(created_note)
    record_import(filename, source_kind, "SUCCESS")
    return result


def clean_description(text):
    """Collapse the whitespace of a wrapped description column."""

    return " ".join(str(text or "").split())
