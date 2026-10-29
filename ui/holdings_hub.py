"""Holdings hub: tab bar and account filter over the holdings sub-pages.

One sidebar entry ("Holdings") opens this hub; the tab bar at the top
switches the content between asset classes, and the account filter at
the right of the tab bar scopes every tab to one account (or
Unassigned / all accounts), like the Dashboard's filter. Always opens
on Stocks.
"""

import customtkinter as ctk

from database.manager import UNASSIGNED, get_accounts
from ui.coming_soon_page import ComingSoonPage
from ui.holdings_page import HoldingsPage
from ui.mutual_funds_page import MutualFundsPage
from ui.theme import *

TABS = (
    ("Stocks", lambda parent, account_id=None: HoldingsPage(parent, account_id)),
    ("Mutual Funds",
     lambda parent, account_id=None: MutualFundsPage(parent, account_id)),
    ("IPO", lambda parent, account_id=None: ComingSoonPage(
        parent, "IPO",
        "IPO applications and allotments will be tracked here "
        "once an IPO importer is added.")),
    ("Bonds", lambda parent, account_id=None: ComingSoonPage(
        parent, "Bonds",
        "Bond and debenture holdings will appear here once a "
        "bond statement importer is added.")),
    ("US Stocks", lambda parent, account_id=None: ComingSoonPage(
        parent, "US Stocks",
        "US stock holdings will appear here once an "
        "international broker statement importer is added.")),
)


class HoldingsHubPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        self._account_id = None  # None = every account

        # ---------------- Tab bar + account filter ---------------- #

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=PADDING, pady=(24, 4))

        self.tab_buttons = {}
        for name, _factory in TABS:
            btn = ctk.CTkButton(
                bar,
                text=name,
                width=150,
                height=36,
                font=SMALL_FONT,
                corner_radius=18,
                fg_color="transparent",
                text_color=TEXT,
                hover_color=BORDER,
                command=lambda x=name: self.show_tab(x),
            )
            btn.pack(side="left", padx=4)
            self.tab_buttons[name] = btn

        filter_row = ctk.CTkFrame(bar, fg_color="transparent")
        filter_row.pack(side="right")

        ctk.CTkLabel(
            filter_row,
            text="Account:",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))

        self.account_menu = ctk.CTkOptionMenu(
            filter_row,
            values=self._filter_choices(),
            width=220,
            height=36,
            font=SMALL_FONT,
            command=self._account_changed,
        )
        self.account_menu.set("All accounts")
        self.account_menu.pack(side="left")

        # ---------------- Content ---------------- #

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        self.current_tab = None
        self.current_page = None
        self.show_tab(TABS[0][0])  # always opens on Stocks

    # ---------------- Account filter ---------------- #

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
        # Re-render the current tab under the new filter; the filter
        # choice itself persists across tab switches.
        self.show_tab(self.current_tab)

    # ---------------- Tab switching ---------------- #

    def show_tab(self, name):
        factory = dict(TABS).get(name)
        if factory is None:
            return
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page = factory(self.content, self._account_id)
        self.current_tab = name

        for tab_name, btn in self.tab_buttons.items():
            btn.configure(
                fg_color=ACCENT if tab_name == name else "transparent",
                text_color=SIDEBAR if tab_name == name else TEXT,
                hover_color=BORDER if tab_name != name else ACCENT,
            )
