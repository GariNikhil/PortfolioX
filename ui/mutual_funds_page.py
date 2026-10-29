"""Mutual Funds page: fund-type holdings from the holdings cache.

Mutual funds and ETFs are picked out of the rebuilt holdings cache by
the same name heuristics the dashboard splits use (ELSS / '... FUND'
names, 'GROWWAMC - ...' ETFs), so imported broker positions land here
without a separate importer. A Type column distinguishes the two.
"""

import customtkinter as ctk

from calculations.allocation import fund_or_fno_label
from database.manager import get_holdings
from ui.formatting import format_quantity, format_rupees
from ui.theme import *

_COLUMNS = (
    ("Symbol", 320, "w"),
    ("Type", 120, "w"),
    ("Quantity", 140, "e"),
    ("Avg Price", 160, "e"),
    ("Invested", 200, "e"),
)


class MutualFundsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        for widget in self.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self,
            text="Mutual Funds",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text=self._summary_line(),
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._table()

    def _fund_holdings(self):
        """Holdings classified as Mutual Fund or ETF, input order."""

        funds = []
        for holding in get_holdings():
            label = fund_or_fno_label(str(holding.get("symbol") or ""))
            if label in ("Mutual Fund", "ETF"):
                funds.append((label, holding))
        return funds

    def _summary_line(self):
        funds = self._fund_holdings()
        invested = sum(
            row["invested_amount"] for _, row in funds
        )
        if not funds:
            return (
                "No fund holdings yet - ELSS and ETF positions from "
                "broker imports appear here"
            )
        return (
            f"{len(funds)} fund positions - total invested "
            f"{format_rupees(invested)}"
        )

    def _table(self):
        """Scrollable fund table with a type column, or empty state."""

        funds = self._fund_holdings()
        if not funds:
            return

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PADDING)
        for name, width, anchor in _COLUMNS:
            ctk.CTkLabel(
                header,
                text=name,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
                width=width,
                anchor=anchor,
            ).pack(side="left", padx=8)

        body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND, height=220)
        body.pack(fill="both", expand=True, padx=PADDING, pady=(4, PADDING))

        for label, row in funds:
            line = ctk.CTkFrame(body, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=2)
            for value, (_, width, anchor) in zip(
                (
                    row["symbol"],
                    label,
                    format_quantity(row["quantity"]),
                    format_rupees(row["average_price"]),
                    format_rupees(row["invested_amount"]),
                ),
                _COLUMNS,
            ):
                ctk.CTkLabel(
                    line,
                    text=value,
                    font=BODY_FONT,
                    text_color=TEXT,
                    width=width,
                    anchor=anchor,
                ).pack(side="left", padx=8)
