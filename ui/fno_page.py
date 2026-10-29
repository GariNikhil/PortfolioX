"""F&O page: derivative holdings from the holdings cache.

F&O contracts (NIFTY / BANKNIFTY / stock options and futures, picked
out by the same symbol-shape heuristics the dashboard splits use) get
their own tab so intraday index trades never mix with equity holdings.
Contracts that were sold out leave no holding row - they remain as
transactions on the Transactions page.
"""

import customtkinter as ctk

from calculations.allocation import fund_or_fno_label
from database.manager import get_holdings
from ui.formatting import format_quantity, format_rupees
from ui.theme import *

_COLUMNS = (
    ("Symbol", 320, "w"),
    ("Quantity", 140, "e"),
    ("Avg Price", 160, "e"),
    ("Invested", 200, "e"),
)


class FnoPage(ctk.CTkFrame):

    def __init__(self, parent, account_id=None):
        super().__init__(parent, fg_color=BACKGROUND)
        self._account_id = account_id  # None = every account
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        for widget in self.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self,
            text="F&O",
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

    def _fno_holdings(self):
        """Holdings classified as F&O contracts, input order."""

        return [
            holding for holding in get_holdings(self._account_id)
            if fund_or_fno_label(str(holding.get("symbol") or "")) == "F&O"
        ]

    def _summary_line(self):
        contracts = self._fno_holdings()
        invested = sum(row["invested_amount"] for row in contracts)
        if not contracts:
            return (
                "No open F&O positions - intraday contracts that were "
                "sold out stay as transactions"
            )
        return (
            f"{len(contracts)} open positions - total invested "
            f"{format_rupees(invested)}"
        )

    def _table(self):
        """Scrollable contract table; the summary line covers the empty case."""

        contracts = self._fno_holdings()
        if not contracts:
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

        for row in contracts:
            line = ctk.CTkFrame(body, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=2)
            for value, (_, width, anchor) in zip(
                (
                    row["symbol"],
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
