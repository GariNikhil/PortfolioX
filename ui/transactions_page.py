"""Transactions page: every recorded trade, newest first."""

import customtkinter as ctk

from database.manager import get_transactions
from ui.formatting import format_quantity, format_rupees
from ui.theme import *

_COLUMNS = (
    ("Date", 110, "w"),
    ("Symbol", 300, "w"),
    ("Side", 70, "center"),
    ("Qty", 90, "e"),
    ("Price", 130, "e"),
    ("Charges", 110, "e"),
    ("Net Amount", 150, "e"),
)

_ROWS_SHOWN = 400


class TransactionsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        transactions = get_transactions()

        ctk.CTkLabel(
            self,
            text="Transactions",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text=self._summary_line(transactions),
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._table(transactions)

    def _summary_line(self, transactions):
        if not transactions:
            return "Nothing imported yet."
        buys = sum(t["net_amount"] for t in transactions if t["transaction_type"] == "BUY")
        sells = sum(t["net_amount"] for t in transactions if t["transaction_type"] == "SELL")
        return (
            f"{len(transactions)} trades - bought {format_rupees(buys)}, "
            f"sold {format_rupees(sells)} (net amounts include charges)"
        )

    def _table(self, transactions):
        """Scrollable trade list (capped for UI responsiveness)."""

        if not transactions:
            ctk.CTkLabel(
                self,
                text="No transactions yet - import a broker file to get started.",
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

        for row in transactions[:_ROWS_SHOWN]:
            side = row["transaction_type"]
            line = ctk.CTkFrame(body, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=1)
            values = (
                row["trade_date"],
                row["symbol"],
                side,
                format_quantity(row["quantity"]),
                format_rupees(row["price"]),
                format_rupees(row["brokerage"] + row["taxes"]),
                format_rupees(row["net_amount"]),
            )
            for value, (_, width, anchor) in zip(values, _COLUMNS):
                ctk.CTkLabel(
                    line,
                    text=value,
                    font=BODY_FONT,
                    text_color=SUCCESS if side == "BUY" else WARNING,
                    width=width,
                    anchor=anchor,
                ).pack(side="left", padx=8)

        if len(transactions) > _ROWS_SHOWN:
            ctk.CTkLabel(
                body,
                text=f"Showing the {_ROWS_SHOWN} most recent of "
                     f"{len(transactions)} trades (Reports page will export all).",
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=8)
