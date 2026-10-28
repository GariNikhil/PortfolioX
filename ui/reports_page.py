"""Reports page: export holdings/transactions CSV and a text summary.

The report content is produced by the pure writers in reports.writer;
this page only asks where to save each file and reports the result.
"""

import tkinter.filedialog
from pathlib import Path

import customtkinter as ctk

from database.manager import get_holdings, get_portfolio_summary, get_transactions
from reports.writer import holdings_csv, portfolio_text_report, transactions_csv
from ui.formatting import format_rupees
from ui.theme import *


class ReportsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="Demat Report",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 8))

        ctk.CTkLabel(
            self,
            text=self._summary_line(),
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 20))

        # ---------------- Export buttons ---------------- #

        exports = ctk.CTkFrame(self, fg_color="transparent")
        exports.pack(pady=6)

        ctk.CTkButton(
            exports,
            text="Export holdings (CSV)",
            width=260,
            command=self.export_holdings,
        ).grid(row=0, column=0, padx=8, pady=8)

        ctk.CTkButton(
            exports,
            text="Export transactions (CSV)",
            width=260,
            command=self.export_transactions,
        ).grid(row=0, column=1, padx=8, pady=8)

        ctk.CTkButton(
            exports,
            text="Save text summary",
            width=260,
            command=self.export_summary,
        ).grid(row=1, column=0, columnspan=2, padx=8, pady=8)

        # ---------------- Result ---------------- #

        self.result_label = ctk.CTkLabel(
            self,
            text="Choose an export above; every file includes all rows.",
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
        )
        self.result_label.pack(pady=16)

    def _summary_line(self):
        summary = get_portfolio_summary()
        return (
            f"{summary['total_holdings']} holdings - "
            f"{summary['total_transactions']} transactions - "
            f"invested {format_rupees(summary['total_invested'])}"
        )

    def export_holdings(self):
        self._save("holdings.csv", "Save holdings CSV",
                   lambda: holdings_csv(get_holdings()))

    def export_transactions(self):
        self._save("transactions.csv", "Save transactions CSV",
                   lambda: transactions_csv(get_transactions()))

    def export_summary(self):
        self._save(
            "portfolio.txt",
            "Save text summary",
            lambda: portfolio_text_report(
                get_portfolio_summary(), get_holdings()
            ),
        )

    def _save(self, default_name, title, content_builder):
        """Ask where to save, write the file, report the outcome."""

        path = tkinter.filedialog.asksaveasfilename(
            title=title,
            defaultextension=Path(default_name).suffix,
            initialfile=default_name,
            filetypes=[
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            Path(path).write_text(content_builder(), encoding="utf-8")
        except OSError as error:
            self.result_label.configure(
                text=f"Save failed: {error}",
                text_color=ERROR,
            )
            return

        self.result_label.configure(
            text=f"Saved {path}",
            text_color=SUCCESS,
        )
