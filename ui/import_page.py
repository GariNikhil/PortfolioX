"""Import page: pick a broker file, run the right importer, see the result.

Encrypted contract-note PDFs get the once-only password flow: on
PasswordRequiredError the page asks for the password (hidden input),
stores it in the encrypted vault, and retries - every later import of
that file runs without asking again.
"""

import tkinter.filedialog
from pathlib import Path

import customtkinter as ctk

from importers.axis_statement import import_axis_statement
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

# label -> (password kind, callable(path, ...) -> ImportResult, needs_date,
#           auto_creates_account). Bank-statement importers auto-create
#           their PERSONAL account on first import (after auto-detection
#           fails), so an unresolved AUTO_DETECT is not an error for them.
_IMPORTERS = {
    "Groww tradebook (CSV / XLSX)": ("GROWW_TRADEBOOK", import_groww_tradebook, False, False),
    "Contract-note Orders sheet (XLSX)": ("CONTRACT_NOTE_ORDERS", import_contract_note, True, False),
    "IIFL Trade Listing (.xls)": ("IIFL_TRADE_LISTING", import_iifl_trade_listing, False, False),
    "stocksledger Portfolio (XLSX)": ("STOCKSLEDGER_PORTFOLIO", import_stocksledger_portfolio, False, False),
    "Holding report (XLSX / CSV)": ("HOLDING_REPORT", import_holding_report, False, False),
    "Mutual fund holdings (XLSX / CSV)": ("MF_HOLDING_REPORT", import_mf_holding_report, False, False),
    "Contract-note PDF": ("CONTRACT_NOTE_PDF", import_contract_note_pdf, False, False),
    "Axis Bank statement (PDF)": ("AXIS_STATEMENT", import_axis_statement, False, True),
    "PNB mPassbook statement (PDF)": ("PNB_MPASSBOOK", import_pnb_statement, False, True),
}

AUTO_DETECT = "Auto-detect from file"


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

        # ---------------- File picker ---------------- #

        picker = ctk.CTkFrame(self, fg_color="transparent")
        picker.pack(fill="x", padx=PADDING)

        self.file_label = ctk.CTkLabel(
            picker,
            text="No file selected",
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.file_label.pack(side="left", padx=(0, 12), fill="x", expand=True)

        ctk.CTkButton(
            picker,
            text="Choose file...",
            width=140,
            command=self.choose_file,
        ).pack(side="left")

        # ---------------- Importer choice ---------------- #

        self.source_menu = ctk.CTkOptionMenu(
            self,
            values=list(_IMPORTERS),
            width=340,
            command=self._source_changed,
        )
        self.source_menu.set("Groww tradebook (CSV / XLSX)")
        self.source_menu.pack(pady=16)

        # ---------------- Orders trade date ---------------- #

        self.date_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.date_label = ctk.CTkLabel(
            self.date_frame,
            text="Trade date (YYYY-MM-DD):",
            font=BODY_FONT,
            text_color=TEXT,
        )
        self.date_label.pack(side="left", padx=(0, 8))
        self.date_entry = ctk.CTkEntry(self.date_frame, width=140, placeholder_text="2023-07-03")
        self.date_entry.pack(side="left")

        # ---------------- Account choice ---------------- #

        account_row = ctk.CTkFrame(self, fg_color="transparent")
        account_row.pack(pady=4)

        ctk.CTkLabel(
            account_row,
            text="Assign to account:",
            font=BODY_FONT,
            text_color=TEXT,
        ).pack(side="left", padx=(0, 8))

        self.account_menu = ctk.CTkOptionMenu(account_row, values=self._account_choices(), width=240)
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
                               "Pick a broker or bank file, choose its format,\n"
                               "and import. Encrypted PDFs ask for their password\n"
                               "once - it is stored encrypted and never asked again.")

    def choose_file(self):
        path = tkinter.filedialog.askopenfilename(
            title="Choose a broker file",
            filetypes=[
                ("Broker files", "*.csv *.xlsx *.xls *.pdf"),
                ("All files", "*.*"),
            ],
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

    def _source_changed(self, choice):
        if _IMPORTERS[choice][2]:
            self.date_frame.pack(pady=4)
        else:
            self.date_frame.pack_forget()

    def run_import(self):
        """Run the chosen importer; report the result or the failure."""

        if self.file_path is None:
            self._report("Choose a file first.", error=True)
            return

        label = self.source_menu.get()
        kind, importer, needs_date, auto_creates = _IMPORTERS[label]

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
            label = self.source_menu.get()
            _kind, importer, needs_date, auto_creates = _IMPORTERS[label]
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
