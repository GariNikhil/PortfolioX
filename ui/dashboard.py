"""Dashboard page: live KPI cards and a top-holdings snapshot.

The account filter scopes every number to one account (or Unassigned /
all accounts); changing it re-renders the cards and the holdings table.
"""

import customtkinter as ctk

from calculations.allocation import (
    asset_allocation,
    market_cap_allocation,
    sector_allocation,
)
from calculations.xirr import xirr, xirr_cashflows
from database.manager import (
    UNASSIGNED,
    get_accounts,
    get_dividends,
    get_holdings,
    get_portfolio_summary,
    get_stock_metadata,
    get_transactions,
)
from ui.formatting import format_quantity, format_rupees, kpi_cards
from ui.theme import *


class DashboardPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(
            parent,
            fg_color=BACKGROUND
        )

        self.pack(fill="both", expand=True)

        self._account_id = None  # None = every account

        # ---------------- Title ---------------- #

        title = ctk.CTkLabel(
            self,
            text="Dashboard",
            font=TITLE_FONT,
            text_color=TEXT
        )

        title.pack(pady=20)

        # ---------------- Account filter ---------------- #

        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=PADDING)

        ctk.CTkLabel(
            filter_row,
            text="Account:",
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))

        self.account_menu = ctk.CTkOptionMenu(
            filter_row,
            values=self._filter_choices(),
            width=260,
            command=self._account_changed,
        )
        self.account_menu.set("All accounts")
        self.account_menu.pack(side="left")

        # ---------------- Renderable body ---------------- #

        # Scrollable: KPI cards + holdings + analysis + chart exceed the
        # window height on smaller screens.
        self.body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        self.body.pack(fill="both", expand=True)

        self._render()

    # ---------------- Filter ---------------- #

    @staticmethod
    def _split_text(split, invested):
        """'(label, amount) ...' pairs -> 'Label 62% · ...' (or a dash)."""

        if invested > 0 and split:
            return " · ".join(
                f"{label} {amount / invested * 100:.0f}%"
                for label, amount in split
            )
        return "—"

    @staticmethod
    def _filter_choices():
        choices = ["All accounts", "Unassigned"]
        choices.extend(account["name"] for account in get_accounts())
        return choices

    def _account_changed(self, choice):
        if choice == "All accounts":
            self._account_id = None
        elif choice == "Unassigned":
            self._account_id = UNASSIGNED
        else:
            for account in get_accounts():
                if account["name"] == choice:
                    self._account_id = account["id"]
                    break
        self._render()

    # ---------------- Content ---------------- #

    def _render(self):
        for widget in self.body.winfo_children():
            widget.destroy()

        self._kpi_cards()
        self._holdings_table()
        self._analysis_section()
        self._chart_placeholder()

    def _kpi_cards(self):
        cards = ctk.CTkFrame(
            self.body,
            fg_color="transparent"
        )

        cards.pack(fill="x", padx=PADDING)

        summary_cards = kpi_cards(get_portfolio_summary(self._account_id))
        for column in range(len(summary_cards)):
            cards.grid_columnconfigure(column, weight=1)

        for column, (name, value, note) in enumerate(summary_cards):

            card = ctk.CTkFrame(
                cards,
                height=CARD_HEIGHT,
                fg_color=CARD,
                border_width=1,
                border_color=BORDER
            )

            # Grid with equal weights: cards shrink/grow with the window
            # instead of clipping the last card off-screen.
            card.grid(row=0, column=column, padx=8, pady=20, sticky="nsew")

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

    def _holdings_table(self):
        """The five largest holdings, or a friendly empty state."""

        section = ctk.CTkLabel(
            self.body,
            text="Top holdings by invested amount",
            font=HEADING_FONT,
            text_color=TEXT
        )

        section.pack(pady=(20, 6))

        frame = ctk.CTkFrame(self.body, fg_color="transparent")
        frame.pack(fill="x", padx=PADDING)

        holdings = sorted(
            get_holdings(self._account_id),
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

    def _analysis_section(self):
        """Portfolio Analysis: seven summary cards under the holdings."""

        section = ctk.CTkLabel(
            self.body,
            text="Portfolio Analysis",
            font=HEADING_FONT,
            text_color=TEXT
        )

        section.pack(pady=(24, 6))

        summary = get_portfolio_summary(self._account_id)
        holdings = get_holdings(self._account_id)
        invested = summary["total_invested"]
        market_value = summary["total_market_value"]

        # XIRR only makes sense when something is actually valued; a
        # zero market value means no prices yet, so show a dash.
        if market_value > 0:
            rate = xirr(xirr_cashflows(
                get_transactions(self._account_id), market_value,
            ))
            xirr_text = f"{rate * 100:+.1f}% / yr" if rate is not None else "—"
        else:
            xirr_text = "—"

        allocation = asset_allocation(holdings)
        allocation_text = self._split_text(allocation, invested)

        dividend_total = sum(row["amount"] for row in get_dividends())

        metadata = {row["symbol"]: row for row in get_stock_metadata()}
        cap_split = market_cap_allocation(holdings, metadata)
        sector_split = sector_allocation(holdings, metadata)
        cap_text = self._split_text(cap_split, invested)
        sector_text = self._split_text(sector_split, invested)

        cards = (
            ("Current Holdings", str(len(holdings)),
             "open positions"),
            ("Invested", format_rupees(invested),
             "across all symbols"),
            ("XIRR", xirr_text,
             "money-weighted return"),
            ("Market Cap", cap_text,
             "large / mid / small cap mix"),
            ("Sector Allocation", sector_text,
             "by invested amount"),
            ("Asset Allocation", allocation_text,
             "by invested amount"),
            ("Dividends", format_rupees(dividend_total),
             "recorded credits"),
        )

        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="x", padx=PADDING)

        per_row = 4
        for index, (name, value, note) in enumerate(cards):
            row, column = divmod(index, per_row)
            grid.grid_rowconfigure(row, weight=1)
            grid.grid_columnconfigure(column, weight=1)

            # Long split strings (cap / sector mixes) wrap to two or
            # three lines in a taller card instead of overflowing.
            value_size = 20
            card_height = 110
            wraplength = 0
            if len(value) > 44:
                value_size, card_height, wraplength = 12, 140, 190
            elif len(value) > 26:
                value_size, wraplength = 14, 190

            card = ctk.CTkFrame(
                grid,
                height=card_height,
                fg_color=CARD,
                border_width=1,
                border_color=BORDER,
            )
            card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")
            card.pack_propagate(False)

            ctk.CTkLabel(
                card,
                text=name,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=(14, 2))

            ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(FONT_FAMILY, value_size, "bold"),
                text_color=TEXT,
                wraplength=wraplength or 0,
                justify="center",
            ).pack(padx=6)

            ctk.CTkLabel(
                card,
                text=note,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
            ).pack()

    def _chart_placeholder(self):
        chart = ctk.CTkFrame(
            self.body,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER
        )

        chart.pack(
            fill="x",
            padx=PADDING,
            pady=PADDING
        )

        ctk.CTkLabel(
            chart,
            text="📈 Portfolio Growth Chart\n(Coming Soon)",
            font=HEADING_FONT,
            text_color=TEXT_SECONDARY
        ).pack(pady=80)
