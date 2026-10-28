"""Dividend Report page: per-symbol dividend totals from the DB.

A read-only summary over database.manager.get_dividends(): one line
per symbol with count and total, plus a grand total.
"""

import customtkinter as ctk

from database.manager import get_dividends
from ui.formatting import format_rupees
from ui.theme import *


class DividendReportPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="💵 Dividend Report",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Dividend income per symbol, newest credit first.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._table()

    def _table(self):
        dividends = get_dividends()

        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

        if not dividends:
            ctk.CTkLabel(
                frame,
                text="No dividends recorded yet — add them on the "
                     "Dividends page.",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
            ).pack(padx=16, pady=16, anchor="w")
            return

        per_symbol = {}
        for row in dividends:
            stats = per_symbol.setdefault(row["symbol"],
                                          {"count": 0, "total": 0.0})
            stats["count"] += 1
            stats["total"] += float(row["amount"] or 0)

        grand_total = sum(stats["total"] for stats in per_symbol.values())

        ctk.CTkLabel(
            frame,
            text=f"{len(per_symbol)} symbols · "
                 f"grand total {format_rupees(grand_total)}",
            font=HEADING_FONT, text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16)
        for text, width, anchor in (
            ("Symbol", 280, "w"), ("Credits", 120, "w"), ("Total", 180, "e"),
        ):
            ctk.CTkLabel(header, text=text, width=width, anchor=anchor,
                         font=SMALL_FONT, text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=2)

        for symbol in sorted(per_symbol,
                             key=lambda s: per_symbol[s]["total"],
                             reverse=True):
            stats = per_symbol[symbol]
            line = ctk.CTkFrame(frame, fg_color="transparent")
            line.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(line, text=symbol, width=280, anchor="w",
                         font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=str(stats["count"]), width=120,
                         anchor="w", font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=format_rupees(stats["total"]), width=180,
                         anchor="e", font=BODY_FONT, text_color=SUCCESS
                         ).pack(side="left", padx=2)
