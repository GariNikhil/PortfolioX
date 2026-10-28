import customtkinter as ctk

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

        card_names = [
            "Portfolio Value",
            "Today's P&L",
            "Overall Profit",
            "Total Return"
        ]

        for name in card_names:

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
            ).pack(pady=(18, 8))

            ctk.CTkLabel(
                card,
                text="₹0.00",
                font=TITLE_FONT,
                text_color=TEXT
            ).pack()

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