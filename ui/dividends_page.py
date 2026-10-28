"""Dividends page: record dividends and see per-symbol totals.

Rows come from database.manager.get_dividends(); adding uses
add_dividend with an ISO date. Amounts are rupees.
"""

import customtkinter as ctk

from database.manager import add_dividend, get_dividends
from importers.common import normalize_date
from ui.formatting import format_rupees
from ui.theme import *


class DividendsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        self._status_label = None

        ctk.CTkLabel(
            self,
            text="💰 Dividends",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Dividend credits per symbol. Amounts are gross rupees.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._add_form()
        self._table_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        self._table_frame.pack(fill="both", expand=True,
                               padx=PADDING, pady=(0, PADDING))
        self._refresh()

    # ---------------- Add form ---------------- #

    def _add_form(self):
        form = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        form.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        ctk.CTkLabel(
            form, text="Record a dividend",
            font=HEADING_FONT, text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 8))

        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(row, text="Symbol",
                     font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._symbol_entry = ctk.CTkEntry(row, width=200)
        self._symbol_entry.grid(row=0, column=1, padx=(0, 20))

        ctk.CTkLabel(row, text="Date (YYYY-MM-DD)",
                     font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).grid(row=0, column=2, sticky="w", padx=(0, 8))
        self._date_entry = ctk.CTkEntry(row, width=140)
        self._date_entry.grid(row=0, column=3, padx=(0, 20))

        ctk.CTkLabel(row, text="Amount (₹)",
                     font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).grid(row=0, column=4, sticky="w", padx=(0, 8))
        self._amount_entry = ctk.CTkEntry(row, width=120)
        self._amount_entry.grid(row=0, column=5, padx=(0, 20))

        ctk.CTkButton(row, text="Add", width=100,
                      command=self._add).grid(row=0, column=6)

    def _add(self):
        symbol = self._symbol_entry.get().strip().upper()
        amount_text = self._amount_entry.get().strip()

        try:
            dividend_date = normalize_date(self._date_entry.get().strip())
        except ValueError:
            self._flash("⚠ Date must be YYYY-MM-DD", ERROR)
            return

        try:
            amount = float(amount_text)
        except ValueError:
            self._flash("⚠ Amount must be a number", ERROR)
            return

        if not symbol or amount <= 0:
            self._flash("⚠ Symbol and a positive amount are required", ERROR)
            return

        add_dividend(symbol, dividend_date, amount)
        self._symbol_entry.delete(0, "end")
        self._date_entry.delete(0, "end")
        self._amount_entry.delete(0, "end")
        self._flash(f"✔ Dividend recorded for {symbol}", SUCCESS)
        self._refresh()

    # ---------------- Table ---------------- #

    def _refresh(self):
        for child in self._table_frame.winfo_children():
            child.destroy()

        dividends = get_dividends()

        if not dividends:
            ctk.CTkLabel(
                self._table_frame,
                text="No dividends recorded yet. Add one above, or they "
                     "will arrive with a dividend report importer later.",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
            ).pack(padx=16, pady=16, anchor="w")
            return

        total = sum(row["amount"] for row in dividends)
        ctk.CTkLabel(
            self._table_frame,
            text=f"{len(dividends)} dividends · total {format_rupees(total)}",
            font=HEADING_FONT, text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 8))

        header = ctk.CTkFrame(self._table_frame, fg_color="transparent")
        header.pack(fill="x", padx=16)
        for text, width, anchor in (
            ("Symbol", 240, "w"), ("Date", 160, "w"),
            ("Amount", 160, "e"),
        ):
            ctk.CTkLabel(header, text=text, width=width, anchor=anchor,
                         font=SMALL_FONT, text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=2)

        for row in dividends:
            line = ctk.CTkFrame(self._table_frame, fg_color="transparent")
            line.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(line, text=row["symbol"], width=240, anchor="w",
                         font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=row["dividend_date"], width=160,
                         anchor="w", font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=format_rupees(row["amount"]), width=160,
                         anchor="e", font=BODY_FONT, text_color=SUCCESS
                         ).pack(side="left", padx=2)

    # ---------------- Feedback ---------------- #

    def _flash(self, message, color):
        if self._status_label is not None:
            self._status_label.destroy()
        self._status_label = ctk.CTkLabel(
            self, text=message, font=SMALL_FONT, text_color=color,
        )
        self._status_label.pack(pady=(0, 8))
