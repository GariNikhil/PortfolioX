"""Operator CLI: walk the broker archive and import every recognized file.

Usage (from the project root):

    .\\.venv\\Scripts\\python.exe tools\\import_broker_files.py [options]

Routes files under --root (default referance/stock) to the right importer
by name/location:

- ``Trade_Listing*.xls``            -> IIFL Trade Listing
- ``*stocksledger*.xlsx``           -> stocksledger Portfolio snapshot
- PDFs in a ``CONTRACT NOTE`` folder or named ``CONTRACT NOTE*`` /
  ``trade_details*``                -> contract-note PDF importer
- other ``.xlsx`` workbooks         -> contract-note Orders sheet (needs
  ``--orders-date``, because Orders rows carry no dates)

Everything else is reported as skipped, not guessed at.

Encrypted PDFs: the password comes from the vault
(``security/vault.py``). When a file has no stored password it is
reported as PASSWORD REQUIRED; re-run with ``--ask-passwords`` in a real
terminal to be prompted once per password (getpass), which stores it and
retries — every later run is fully automatic. ``--try-derived``
additionally tries documented derived candidates (PAN case variants,
client code) harvested from the *unencrypted* notes in the same tree, and
stores whichever one works.

Safety rails:

- ``--db PATH`` points the run at a scratch database; without it the tool
  targets the live ``data/portfoliox.db`` and refuses to write unless
  ``--yes`` is also given.
- ``--dry-run`` only prints the routing decisions.
"""

import argparse
import getpass
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import db  # noqa: E402  (path setup must come first)
from database.schema import ensure_schema  # noqa: E402
from importers.common import ImportFileError  # noqa: E402
from security.vault import (  # noqa: E402
    PasswordRequiredError,
    VaultError,
    store_password,
)
from importers.contract_note import import_contract_note  # noqa: E402
from importers.groww import import_groww_tradebook  # noqa: E402
from importers.iifl import import_iifl_trade_listing  # noqa: E402
from importers.pdf_note import (  # noqa: E402
    SOURCE_KIND as PDF_KIND,
    import_contract_note_pdf,
    parse_contract_note_pdf,
)
from importers.stocksledger import import_stocksledger_portfolio  # noqa: E402

PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
CLIENT_CODE_PATTERN = re.compile(r"Unique Client Code:\s*(\d{6,})")

# Outcome labels for the per-file report.
OK = "OK"
NEEDS_PASSWORD = "PASSWORD REQUIRED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"


def route_file(path, orders_date):
    """Decide what to do with one file: (action, note) or (None, reason)."""

    name = path.name.lower()

    if name.endswith(".xls") and name.startswith("trade_listing"):
        return "iifl", ""
    if name.endswith(".xlsx") and "stocksledger" in name:
        return "stocksledger", ""
    if name.endswith(".pdf") and (
        "contract note" in str(path.parent).lower()
        or "contract note" in name
        or name.startswith("trade_details")
    ):
        return "pdf", ""
    if name.endswith(".xlsx"):
        if "stocksledger" not in name and orders_date:
            return "orders", ""
        return None, "Orders workbook needs --orders-date (rows carry no dates)"
    if name.endswith((".csv", ".xls")):
        return None, "no recognized importer for this file"
    return None, "not an importable file type"


def harvest_derived_candidates(root):
    """PAN / client-code values found in *unencrypted* notes under root.

    These are the documented password conventions for this broker's
    archive; only values readable from files the user can already open are
    used, and nothing is written anywhere unless a candidate actually
    decrypts a file.
    """

    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    values = set()
    for pdf in sorted(root.rglob("*.pdf")):
        try:
            reader = PdfReader(str(pdf))
            if reader.is_encrypted:
                continue
            text = " ".join(
                (page.extract_text() or "") for page in reader.pages[:2]
            )
        except Exception:
            continue
        values.update(PAN_PATTERN.findall(text))
        values.update(CLIENT_CODE_PATTERN.findall(text))

    candidates = set()
    for value in values:
        candidates.add(value)
        candidates.add(value.lower())
        candidates.add(value.capitalize())
    return sorted(candidates)[:12]


def looks_like_contract_note(path):
    """Pre-flight for routed PDFs: does the readable text carry a Trade date?

    Encrypted files cannot be inspected, so they are assumed to be contract
    notes (the vault flow will prove or reject that). Unencrypted files
    that lack the header — account-opening forms, ledgers, statements — are
    skipped here so they never reach the importer or the audit trail.
    """

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            return True
        text = " ".join(
            (reader.pages[index].extract_text() or "")
            for index in range(min(2, len(reader.pages)))
        )
        return "Trade date" in text
    except Exception:
        return False


def import_with_vault(path, derived_candidates=(), ask_passwords=False):
    """Import one PDF, prompting/deriving the password at most once.

    Returns (result_or_None, label, detail). The password, once it works,
    is stored in the vault so this file (and matching files) never prompt
    again.
    """

    try:
        return import_contract_note_pdf(path), OK, ""
    except PasswordRequiredError:
        pass  # fall through to the one-time prompt

    for candidate in derived_candidates:
        try:
            parse_contract_note_pdf(path)  # proves the password works
        except PasswordRequiredError:
            continue
        except Exception:
            continue
        store_password(PDF_KIND, candidate)
        print(f"    derived password accepted and stored for {path.name}")
        return import_contract_note_pdf(path), OK, ""

    if not ask_passwords:
        return None, NEEDS_PASSWORD, "no stored password (run with --ask-passwords)"

    password = prompt_for_password(path)
    if password is None:
        return None, NEEDS_PASSWORD, "prompt declined"

    store_password(PDF_KIND, password)
    try:
        return import_contract_note_pdf(path), OK, ""
    except PasswordRequiredError:
        print(f"    stored password was rejected for {path.name}")
        return None, NEEDS_PASSWORD, "stored password was rejected"
    except Exception as error:
        return None, FAILED, str(error)


def prompt_for_password(path):
    """Ask once for the file's password.

    Only called when the operator passed --ask-passwords: a batch run
    (cron, agent, redirected console) must never block on hidden input.
    Returns None when the prompt is declined or empty.
    """

    try:
        password = getpass.getpass(f"Password for {path.name}: ")
    except (EOFError, KeyboardInterrupt):
        return None
    return password or None


def run_import(action, path, orders_date, ask_passwords=False):
    """Dispatch one routed file. Returns (result_or_None, label, detail)."""

    try:
        if action == "iifl":
            return import_iifl_trade_listing(path), OK, ""
        if action == "stocksledger":
            return import_stocksledger_portfolio(path), OK, ""
        if action == "orders":
            return import_contract_note(path, orders_date), OK, ""
        if action == "pdf":
            return import_with_vault(path, ask_passwords=ask_passwords)
    except ImportFileError as error:
        return None, FAILED, str(error)
    except VaultError as error:
        return None, FAILED, f"vault problem - {error}"
    return None, SKIPPED, "unrouted file"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Import every recognized broker file under a folder."
    )
    parser.add_argument("--root", default=str(PROJECT_ROOT / "referance" / "stock"),
                        help="folder to walk (default: referance/stock)")
    parser.add_argument("--db", help="database file to use (default: data/portfoliox.db)")
    parser.add_argument("--orders-date",
                        help="trade date for Orders workbooks (YYYY-MM-DD); "
                             "they carry no dates of their own")
    parser.add_argument("--try-derived", action="store_true",
                        help="try PAN/client-code password candidates harvested "
                             "from unencrypted notes before prompting")
    parser.add_argument("--ask-passwords", action="store_true",
                        help="prompt (hidden input) for encrypted files that "
                             "have no stored password yet; without this flag "
                             "they are reported and skipped")
    parser.add_argument("--dry-run", action="store_true",
                        help="only print what would be imported")
    parser.add_argument("--yes", action="store_true",
                        help="allow writing the live data/portfoliox.db")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        parser.error(f"--root is not a folder: {root}")

    if args.db:
        db.DB_PATH = Path(args.db)
    elif not args.yes and not args.dry_run:
        parser.error(
            "refusing to write the live data/portfoliox.db without --yes "
            "(use --db for a scratch database, or --dry-run to just plan)"
        )

    if not args.dry_run:
        ensure_schema()

    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and not path.name.startswith(("~$", "README"))
    )

    derived = harvest_derived_candidates(root) if args.try_derived else []
    if derived:
        print(f"derived password candidates: {len(derived)} (values from unencrypted notes)")

    print(f"walking {root} ({len(files)} files)\n")

    totals = {OK: 0, NEEDS_PASSWORD: 0, FAILED: 0, SKIPPED: 0}
    imported_rows = 0
    for path in files:
        relative = path.relative_to(root)
        action, note = route_file(path, args.orders_date)
        if action is None:
            totals[SKIPPED] += 1
            print(f"  SKIP   {relative}  ({note})")
            continue

        if args.dry_run:
            print(f"  PLAN   {relative}  -> {action}")
            continue

        if action == "pdf" and not looks_like_contract_note(path):
            totals[SKIPPED] += 1
            print(f"  SKIP   {relative}  (not a contract note: no Trade date header)")
            continue

        result, label, detail = run_import(
            action, path, args.orders_date, ask_passwords=args.ask_passwords
        )
        if label == OK:
            totals[OK] += 1
            imported_rows += result.imported
            print(f"  {label:<16} {relative}  -> {result.summary()}")
            for failure in result.failures:
                print(f"                   row {failure.row_number}: {failure.reason}")
        else:
            totals[label] += 1
            print(f"  {label:<16} {relative}  {detail}")

    print(
        f"\ndone: {totals[OK]} imported ({imported_rows} rows), "
        f"{totals[NEEDS_PASSWORD]} need a password, "
        f"{totals[FAILED]} failed, {totals[SKIPPED]} skipped"
    )
    if totals[NEEDS_PASSWORD]:
        print(
            "encrypted files are waiting: re-run with --ask-passwords in a "
            "real terminal and enter each password once (stored in the "
            "vault afterwards)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
