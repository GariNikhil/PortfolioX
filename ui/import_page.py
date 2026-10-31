"""Import page: pick a broker file, run the right importer, see the result.

Three steps, in order:

1. **File type** - the physical format the file comes as (XLSX, XLS,
   CSV, PDF). Different brokers and banks export the same data in
   different shapes, so the format is chosen first.
2. **File for** - what the file is for (tradebook, contract note,
   holding statement, bank statement...). The options are filtered to
   the purposes that exist for the chosen file type, and the
   (type, purpose) pair selects the actual importer.
3. **Select a/c** - which account the rows belong to (or auto-detect).

Encrypted contract-note PDFs get the once-only password flow: on
PasswordRequiredError the page asks for the password (hidden input),
stores it in the encrypted vault, and retries - every later import of
that file runs without asking again.
"""

import tkinter.filedialog
from functools import partial
from pathlib import Path

import customtkinter as ctk

from importers.axis_statement import import_axis_statement
from importers.bank_statement_tabular import import_bank_statement_tabular
from importers.contract_note import import_contract_note
from importers.groww import import_groww_tradebook
from importers.holding_report import import_holding_report
from importers.iifl import import_iifl_trade_listing
from importers.mf_holding_report import import_mf_holding_report
from importers.pdf_note import import_contract_note_pdf
from importers.pnb_statement import import_pnb_statement
from importers.stocksledger import import_stocksledger_portfolio
from importers.common import detect_account
from database.backup import backup_database
from database.manager import get_accounts
from security.vault import PasswordRequiredError, VaultError, store_password
from ui.theme import *

# Importer spec: (password kind, callable(path, ...) -> ImportResult,
# needs_date, auto_creates_account). Bank-statement importers auto-create
# their PERSONAL account on first import (after auto-detection fails),
# so an unresolved AUTO_DETECT is not an error for them.
_GROWW = ("GROWW_TRADEBOOK", import_groww_tradebook, False, False)
_HOLDING = ("HOLDING_REPORT", import_holding_report, False, False)
_MF_HOLDING = ("MF_HOLDING_REPORT", import_mf_holding_report, False, False)

# US stocks and bonds reuse the generic tradebook / holding-report
# parsers with their own audit kinds and snapshot sources, so their
# rows are filed and replaced independently of Indian stocks.
_US_TRADEBOOK = (
    "US_TRADEBOOK",
    partial(import_groww_tradebook, source_kind="US_TRADEBOOK"),
    False, False,
)
_US_HOLDING = (
    "US_HOLDING_REPORT",
    partial(import_holding_report, source="us_holding_report"),
    False, False,
)
_BOND_TRADEBOOK = (
    "BOND_TRADEBOOK",
    partial(import_groww_tradebook, source_kind="BOND_TRADEBOOK"),
    False, False,
)
_BOND_HOLDING = (
    "BOND_HOLDING_REPORT",
    partial(import_holding_report, source="bond_holding_report"),
    False, False,
)

# Spreadsheet bank statements (banks also export Excel, not just PDF);
# bank_name names the auto-created PERSONAL account on first import.
_AXIS_XLS = (
    None,
    partial(import_bank_statement_tabular, bank_name="Axis Bank"),
    False, True,
)
_PNB_XLS = (
    None,
    partial(import_bank_statement_tabular, bank_name="Punjab National Bank"),
    False, True,
)

# (file type, purpose) -> importer spec. The file type is the physical
# format (step 1), the purpose is what the file is for (step 2); a
# purpose appears under every type a broker might export it as. Where
# two banks share a type and purpose, the label names the bank.
_IMPORTERS = {
    ("XLSX", "Tradebook / transaction history"): _GROWW,
    ("CSV", "Tradebook / transaction history"): _GROWW,
    ("XLS", "Trade listing (IIFL)"):
        ("IIFL_TRADE_LISTING", import_iifl_trade_listing, False, False),
    ("XLSX", "Contract note - Orders sheet"):
        ("CONTRACT_NOTE_ORDERS", import_contract_note, True, False),
    ("PDF", "Contract note"):
        ("CONTRACT_NOTE_PDF", import_contract_note_pdf, False, False),
    ("XLSX", "Portfolio snapshot (stocksledger)"):
        ("STOCKSLEDGER_PORTFOLIO", import_stocksledger_portfolio, False, False),
    ("XLSX", "Holding statement (stocks)"): _HOLDING,
    ("CSV", "Holding statement (stocks)"): _HOLDING,
    ("XLSX", "Mutual fund holdings"): _MF_HOLDING,
    ("CSV", "Mutual fund holdings"): _MF_HOLDING,
    ("XLSX", "Tradebook (US stocks)"): _US_TRADEBOOK,
    ("CSV", "Tradebook (US stocks)"): _US_TRADEBOOK,
    ("XLSX", "Holding statement (US stocks)"): _US_HOLDING,
    ("CSV", "Holding statement (US stocks)"): _US_HOLDING,
    ("XLSX", "Tradebook (bonds)"): _BOND_TRADEBOOK,
    ("CSV", "Tradebook (bonds)"): _BOND_TRADEBOOK,
    ("XLSX", "Holding statement (bonds)"): _BOND_HOLDING,
    ("CSV", "Holding statement (bonds)"): _BOND_HOLDING,
    ("PDF", "Bank statement - Axis Bank"):
        ("AXIS_STATEMENT", import_axis_statement, False, True),
    ("PDF", "Bank statement - PNB mPassbook"):
        ("PNB_MPASSBOOK", import_pnb_statement, False, True),
    ("XLSX", "Bank statement - Axis Bank"): _AXIS_XLS,
    ("CSV", "Bank statement - Axis Bank"): _AXIS_XLS,
    ("XLSX", "Bank statement - PNB"): _PNB_XLS,
    ("CSV", "Bank statement - PNB"): _PNB_XLS,
}

FILE_TYPES = ("XLSX", "XLS", "CSV", "PDF")

# File dialog filter per file type.
_FILE_PATTERNS = {
    "XLSX": ("Excel workbooks", "*.xlsx"),
    "XLS": ("Legacy Excel files", "*.xls"),
    "CSV": ("CSV files", "*.csv"),
    "PDF": ("PDF files", "*.pdf"),
}

# Extension each file type should have; a mismatch is reported before
# the importer gets a file it cannot parse.
_EXPECTED_SUFFIX = {
    "XLSX": ".xlsx", "XLS": ".xls", "CSV": ".csv", "PDF": ".pdf",
}

AUTO_DETECT = "Auto-detect from file"


def purposes_for(file_type):
    """Purpose labels (step 2 options) available for a file type."""

    return [
        purpose for (ftype, purpose) in _IMPORTERS if ftype == file_type
    ]


class ImportPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        self.file_path = None
        self.backup_path = None

        ctk.CTkLabel(
            self,
            text="Import",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 16))

        # ---------------- 1. File type ---------------- #

        type_row = ctk.CTkFrame(self, fg_color="transparent")
        type_row.pack(fill="x", padx=PADDING, pady=(0, 6))

        ctk.CTkLabel(
            type_row, text="1. File type:", font=BODY_FONT, text_color=TEXT,
            width=110, anchor="w",
        ).pack(side="left")

        self.type_menu = ctk.CTkOptionMenu(
            type_row, values=list(FILE_TYPES), width=140,
            command=self._type_changed,
        )
        self.type_menu.set("XLSX")
        self.type_menu.pack(side="left")

        # ---------------- 2. File for ---------------- #

        purpose_row = ctk.CTkFrame(self, fg_color="transparent")
        purpose_row.pack(fill="x", padx=PADDING, pady=(0, 6))

        ctk.CTkLabel(
            purpose_row, text="2. File for:", font=BODY_FONT, text_color=TEXT,
            width=110, anchor="w",
        ).pack(side="left")

        self.purpose_menu = ctk.CTkOptionMenu(
            purpose_row, values=purposes_for("XLSX"), width=320,
            command=self._purpose_changed,
        )
        self.purpose_menu.set(purposes_for("XLSX")[0])
        self.purpose_menu.pack(side="left")

        # ---------------- File picker ---------------- #

        picker = ctk.CTkFrame(self, fg_color="transparent")
        picker.pack(fill="x", padx=PADDING, pady=(0, 6))

        ctk.CTkButton(
            picker,
            text="Choose file...",
            width=140,
            command=self.choose_file,
        ).pack(side="left", padx=(110 + 12, 12))

        self.file_label = ctk.CTkLabel(
            picker,
            text="No file selected",
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.file_label.pack(side="left", fill="x", expand=True)

        # ---------------- Orders trade date ---------------- #

        self.date_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.date_label = ctk.CTkLabel(
            self.date_frame,
            text="Trade date (YYYY-MM-DD):",
            font=BODY_FONT,
            text_color=TEXT,
        )
        self.date_label.pack(side="left", padx=(110 + 12, 8))
        self.date_entry = ctk.CTkEntry(self.date_frame, width=140, placeholder_text="2023-07-03")
        self.date_entry.pack(side="left")

        # ---------------- 3. Select a/c ---------------- #

        self.account_row = ctk.CTkFrame(self, fg_color="transparent")
        self.account_row.pack(fill="x", padx=PADDING, pady=(6, 4))

        ctk.CTkLabel(
            self.account_row,
            text="3. Select a/c:",
            font=BODY_FONT,
            text_color=TEXT,
            width=110,
            anchor="w",
        ).pack(side="left")

        self.account_menu = ctk.CTkOptionMenu(
            self.account_row, values=self._account_choices(), width=320,
        )
        self.account_menu.set(self._account_choices()[0])
        self.account_menu.pack(side="left")

        # ---------------- Run ---------------- #

        ctk.CTkButton(
            self,
            text="Import file",
            width=180,
            height=40,
            font=BODY_FONT,
            command=self.run_import,
        ).pack(pady=8)

        # ---------------- Result ---------------- #

        self.result_box = ctk.CTkTextbox(self, font=("Consolas", 13))
        self.result_box.pack(fill="both", expand=True, padx=PADDING, pady=PADDING)
        self.result_box.insert("0.0",
                               "1. File type - the format the file comes as.\n"
                               "2. File for - what the file is for.\n"
                               "3. Select a/c - or auto-detect from the file.\n\n"
                               "Encrypted PDFs ask for their password once -\n"
                               "it is stored encrypted and never asked again.")

    def _importer_spec(self):
        """The (kind, importer, needs_date, auto_creates) for the choice."""

        key = (self.type_menu.get(), self.purpose_menu.get())
        return _IMPORTERS[key]

    def choose_file(self):
        label, pattern = _FILE_PATTERNS[self.type_menu.get()]
        path = tkinter.filedialog.askopenfilename(
            title="Choose the file to import",
            filetypes=[(label, pattern), ("All files", "*.*")],
        )
        if path:
            self.file_path = Path(path)
            self.file_label.configure(text=str(self.file_path), text_color=TEXT)

    @staticmethod
    def _account_choices():
        """Dropdown options; 'Unassigned' maps to account_id None."""

        choices = [AUTO_DETECT, "Unassigned"]
        choices.extend(account["name"] for account in get_accounts())
        return choices

    def _resolve_account_id(self, allow_unresolved=False):
        """The account for this import, resolved from the dropdown.

        'Auto-detect from file' matches the statement's UCC / PAN /
        account number against the stored accounts (so repeated imports
        segregate themselves per account); a specific account wins
        outright; 'Unassigned' maps to None. Returns (account_id, note)
        where note explains an auto-detection for the result box, or
        (None, error) when auto-detection failed - unless
        allow_unresolved (bank-statement importers): then AUTO_DETECT
        hands None to the importer untouched, because bank statements
        are detected by ACCOUNT NUMBER inside the import flow - never
        by PAN, which every account of the same person shares.
        """

        choice = self.account_menu.get()
        if choice == AUTO_DETECT:
            if allow_unresolved:
                return None, None
            account = detect_account(self.file_path)
            if account is None:
                return None, (
                    "Could not identify the account from the file "
                    "(no matching UCC / PAN / a/c no). Pick an account "
                    "manually - the first import fills the account's "
                    "details from the file, so later imports auto-detect."
                )
            return account["id"], f"Account auto-detected: {account['name']}"
        if choice == "Unassigned":
            return None, None
        for account in get_accounts():
            if account["name"] == choice:
                return account["id"], None
        return None, None

    def _type_changed(self, file_type):
        """New file type: refill the purposes and refresh the date row."""

        purposes = purposes_for(file_type)
        self.purpose_menu.configure(values=purposes)
        self.purpose_menu.set(purposes[0])
        self._sync_date_row()

    def _purpose_changed(self, _purpose):
        self._sync_date_row()

    def _sync_date_row(self):
        """Show the trade-date row only for importers that need one.

        `before=` keeps it between the file picker and the a/c row no
        matter when it gets (re)packed.
        """

        if self._importer_spec()[2]:
            self.date_frame.pack(
                fill="x", padx=PADDING, pady=(0, 6), before=self.account_row,
            )
        else:
            self.date_frame.pack_forget()

    def run_import(self):
        """Run the chosen importer; report the result or the failure."""

        if self.file_path is None:
            self._report("Choose a file first.", error=True)
            return

        expected = _EXPECTED_SUFFIX[self.type_menu.get()]
        if self.file_path.suffix.lower() != expected:
            self._report(
                f"File type is {self.type_menu.get()} ({expected}) but the "
                f"selected file is '{self.file_path.name}'. Pick the file "
                "type that matches the file, or choose another file.",
                error=True,
            )
            return

        kind, importer, needs_date, auto_creates = self._importer_spec()

        account_id, note = self._resolve_account_id(allow_unresolved=auto_creates)
        if note is not None and account_id is None:
            self._report(note, error=True)
            return

        # One snapshot per import attempt: a failed attempt that wrote
        # nothing (e.g. cancelled password dialog) leaves it valid for the
        # retry below, so no second backup is needed.
        self.backup_path = backup_database()

        try:
            if needs_date:
                result = importer(self.file_path, self.date_entry.get().strip(),
                                  account_id=account_id)
            else:
                result = importer(self.file_path, account_id=account_id)
        except PasswordRequiredError:
            self._handle_missing_password(kind)
            return
        except Exception as error:
            self._report(f"Import failed: {error}", error=True)
            return

        lines = [result.summary()]
        if note:
            lines.append(note)
        if self.backup_path:
            lines.append(f"Pre-import backup: {self.backup_path}")
        if result.failures:
            lines.append("Rejected rows:")
            lines.extend(
                f"  row {failure.row_number}: {failure.reason}"
                for failure in result.failures
            )
        self._report("\n".join(lines))

    def _handle_missing_password(self, kind):
        """The once-only password prompt: ask, store, retry."""

        dialog = ctk.CTkInputDialog(
            text=f"{self.file_path.name} is password-protected.\n"
                 "Enter the password once - it will be stored encrypted\n"
                 "and never asked again:",
            title="Password required",
        )
        password = dialog.get_input()

        if not password or not password.strip():
            self._report("No password entered - import cancelled.", error=True)
            return

        try:
            store_password(kind, password.strip())
            _kind, importer, needs_date, auto_creates = self._importer_spec()
            account_id, note = self._resolve_account_id(
                allow_unresolved=auto_creates,
            )
            if note is not None and account_id is None:
                self._report(note, error=True)
                return
            if needs_date:
                result = importer(self.file_path, self.date_entry.get().strip(),
                                  account_id=account_id)
            else:
                result = importer(self.file_path, account_id=account_id)
        except Exception as error:
            # includes a rejected password (PasswordRequiredError again)
            self._report(f"Import failed: {error}", error=True)
            return

        self._report(
            "Password stored in the vault (won't ask again).\n" + result.summary()
        )

    def _report(self, text, error=False):
        self.result_box.delete("0.0", "end")
        self.result_box.insert("0.0", text)
        self.result_box.configure(text_color=ERROR if error else TEXT)
