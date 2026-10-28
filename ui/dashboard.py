"""Dashboard page: live KPI cards and a top-holdings snapshot."""

import customtkinter as ctk

from database.manager import get_holdings, get_portfolio_summary
from ui.formatting import format_quantity, format_rupees, kpi_cards
from ui.theme import *


class DashboardPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(
            parent,
            fg_color=BACKGROUND
        )

        self.pack(fill="both", expand=True)

        # ---------------- Title ---------------- #

        title = ctk.CTkLabel(
            self,
            text="Dashboard",
            font=TITLE_FONT,
            text_color=TEXT
        )

        title.pack(pady=20)

        # ---------------- KPI Cards ---------------- #

        cards = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        cards.pack(fill="x", padx=PADDING)

        for name, value, note in kpi_cards(get_portfolio_summary()):

            card = ctk.CTkFrame(
                cards,
                width=CARD_WIDTH,
                height=CARD_HEIGHT,
                fg_color=CARD,
                border_width=1,
                border_color=BORDER
            )

            card.pack(side="left", padx=10, pady=20)

            card.pack_propagate(False)

            ctk.CTkLabel(
                card,
                text=name,
                font=HEADING_FONT,
                text_color=TEXT_SECONDARY
            ).pack(pady=(18, 4))

            ctk.CTkLabel(
                card,
                text=value,
                font=TITLE_FONT,
                text_color=TEXT
            ).pack()

            ctk.CTkLabel(
                card,
                text=note,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY
            ).pack()

        # ---------------- Top Holdings ---------------- #

        section = ctk.CTkLabel(
            self,
            text="Top holdings by invested amount",
            font=HEADING_FONT,
            text_color=TEXT
        )

        section.pack(pady=(20, 6))

        self._holdings_table()

        # ---------------- Chart Placeholder ---------------- #

        chart = ctk.CTkFrame(
            self,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER
        )

        chart.pack(
            fill="both",
            expand=True,
            padx=PADDING,
            pady=PADDING
        )

        ctk.CTkLabel(
            chart,
            text="📈 Portfolio Growth Chart\n(Coming Soon)",
            font=HEADING_FONT,
            text_color=TEXT_SECONDARY
        ).pack(expand=True)

    def _holdings_table(self):
        """The five largest holdings, or a friendly empty state."""

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=PADDING)

        holdings = sorted(
            get_holdings(),
            key=lambda row: row["invested_amount"],
            reverse=True,
        )[:5]

        if not holdings:
            ctk.CTkLabel(
                frame,
                text="No holdings yet - import a broker file to get started.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY
            ).pack(pady=10)
            return

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x")
        for column, width in (("Symbol", 320), ("Qty", 120), ("Avg Price", 160), ("Invested", 200)):
            ctk.CTkLabel(
                header,
                text=column,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
                width=width,
                anchor="w" if column == "Symbol" else "e",
            ).pack(side="left", padx=8)

        for row in holdings:
            line = ctk.CTkFrame(frame, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(
                line, text=row["symbol"], font=BODY_FONT, text_color=TEXT,
                width=320, anchor="w",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=format_quantity(row["quantity"]), font=BODY_FONT,
                text_color=TEXT, width=120, anchor="e",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=format_rupees(row["average_price"]), font=BODY_FONT,
                text_color=TEXT, width=160, anchor="e",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=format_rupees(row["invested_amount"]), font=BODY_FONT,
                text_color=TEXT, width=200, anchor="e",
            ).pack(side="left", padx=8)
