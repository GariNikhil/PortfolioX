"""Import page: pick a broker file, run the right importer, see the result.

Encrypted contract-note PDFs get the once-only password flow: on
PasswordRequiredError the page asks for the password (hidden input),
stores it in the encrypted vault, and retries - every later import of
that file runs without asking again.
"""

import tkinter.filedialog
from pathlib import Path

import customtkinter as ctk

from importers.contract_note import import_contract_note
from importers.groww import import_groww_tradebook
from importers.holding_report import import_holding_report
from importers.iifl import import_iifl_trade_listing
from importers.pdf_note import import_contract_note_pdf
from importers.stocksledger import import_stocksledger_portfolio
from database.backup import backup_database
from database.manager import get_accounts
from security.vault import PasswordRequiredError, VaultError, store_password
from ui.theme import *

# label -> (password kind, callable(path, ...) -> ImportResult, needs_date)
_IMPORTERS = {
    "Groww tradebook (CSV / XLSX)": ("GROWW_TRADEBOOK", import_groww_tradebook, False),
    "Contract-note Orders sheet (XLSX)": ("CONTRACT_NOTE_ORDERS", import_contract_note, True),
    "IIFL Trade Listing (.xls)": ("IIFL_TRADE_LISTING", import_iifl_trade_listing, False),
    "stocksledger Portfolio (XLSX)": ("STOCKSLEDGER_PORTFOLIO", import_stocksledger_portfolio, False),
    "Holding report (XLSX / CSV)": ("HOLDING_REPORT", import_holding_report, False),
    "Contract-note PDF": ("CONTRACT_NOTE_PDF", import_contract_note_pdf, False),
}


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
                               "Pick a broker file, choose its format, and import.\n"
                               "Encrypted PDFs ask for their password once - it is\n"
                               "stored encrypted and never asked again.")

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

        choices = ["Unassigned"]
        choices.extend(account["name"] for account in get_accounts())
        return choices

    def _selected_account_id(self):
        """The account chosen in the dropdown, or None for Unassigned."""

        choice = self.account_menu.get()
        for account in get_accounts():
            if account["name"] == choice:
                return account["id"]
        return None

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
        kind, importer, needs_date = _IMPORTERS[label]

        # One snapshot per import attempt: a failed attempt that wrote
        # nothing (e.g. cancelled password dialog) leaves it valid for the
        # retry below, so no second backup is needed.
        self.backup_path = backup_database()

        try:
            account_id = self._selected_account_id()
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
            importer = _IMPORTERS[label][1]
            account_id = self._selected_account_id()
            if _IMPORTERS[label][2]:
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
