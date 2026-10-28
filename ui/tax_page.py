"""Tax page: per-financial-year (April-March) trading turnover summary.

The numbers come from calculations.allocation.financial_year_summary
over all transactions; turnover is gross qty*price before charges,
which is where tax reporting starts.
"""

import customtkinter as ctk

from calculations.allocation import financial_year_summary
from database.manager import get_transactions
from ui.formatting import format_rupees
from ui.theme import *


class TaxPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="🧾 Tax",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Turnover per financial year (April-March), gross "
                 "quantity × price before charges.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._table()

    def _table(self):
        summary = financial_year_summary(get_transactions())

        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

        if not summary:
            ctk.CTkLabel(
                frame,
                text="No transactions yet.",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
            ).pack(padx=16, pady=16, anchor="w")
            return

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        for text, width, anchor in (
            ("Year", 140, "w"), ("Buys", 90, "w"), ("Sells", 90, "w"),
            ("Buy turnover", 180, "e"), ("Sell turnover", 180, "e"),
        ):
            ctk.CTkLabel(header, text=text, width=width, anchor=anchor,
                         font=SMALL_FONT, text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=2)

        for label, stats in summary:
            line = ctk.CTkFrame(frame, fg_color="transparent")
            line.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(line, text=label, width=140, anchor="w",
                         font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=str(stats["buy_count"]), width=90,
                         anchor="w", font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=str(stats["sell_count"]), width=90,
                         anchor="w", font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=format_rupees(stats["buy_turnover"]),
                         width=180, anchor="e", font=BODY_FONT,
                         text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=format_rupees(stats["sell_turnover"]),
                         width=180, anchor="e", font=BODY_FONT,
                         text_color=TEXT
                         ).pack(side="left", padx=2)

        ctk.CTkLabel(
            frame,
            text="Capital-gains computation (holding-period splits, "
                 "FIFO lots) arrives with a later release.",
            font=SMALL_FONT, text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(10, 12))
