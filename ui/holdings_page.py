"""Holdings page: the full holdings cache as a scrollable table."""

import customtkinter as ctk

from database.manager import get_holdings
from ui.formatting import format_quantity, format_rupees
from ui.theme import *

_COLUMNS = (
    ("Symbol", 320, "w"),
    ("Quantity", 140, "e"),
    ("Avg Price", 160, "e"),
    ("Invested", 200, "e"),
)


class HoldingsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="Stocks",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        summary = ctk.CTkLabel(
            self,
            text=self._summary_line(),
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        )
        summary.pack(pady=(0, 16))

        self._table()

    def _summary_line(self):
        holdings = get_holdings()
        invested = sum(row["invested_amount"] for row in holdings)
        return (
            f"{len(holdings)} open positions - total invested "
            f"{format_rupees(invested)} (market value arrives with live prices)"
        )

    def _table(self):
        """Scrollable holdings table, or a friendly empty state."""

        holdings = get_holdings()

        if not holdings:
            ctk.CTkLabel(
                self,
                text="No holdings yet - import a broker file to get started.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=30)
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

        body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        body.pack(fill="both", expand=True, padx=PADDING, pady=(4, PADDING))

        for row in holdings:
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
