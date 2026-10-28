"""Holdings hub: tab bar over the holdings sub-pages.

One sidebar entry ("Holdings") opens this hub; the tab bar at the top
switches the content between asset classes. Always opens on Stocks.
"""

import customtkinter as ctk

from ui.coming_soon_page import ComingSoonPage
from ui.holdings_page import HoldingsPage
from ui.theme import *

TABS = (
    ("Stocks", lambda parent: HoldingsPage(parent)),
    ("Mutual Funds", lambda parent: ComingSoonPage(
        parent, "Mutual Funds",
        "Mutual fund holdings will appear here once a CAS or "
        "broker statement importer is added.")),
    ("IPO", lambda parent: ComingSoonPage(
        parent, "IPO",
        "IPO applications and allotments will be tracked here "
        "once an IPO importer is added.")),
    ("Bonds", lambda parent: ComingSoonPage(
        parent, "Bonds",
        "Bond and debenture holdings will appear here once a "
        "bond statement importer is added.")),
    ("US Stocks", lambda parent: ComingSoonPage(
        parent, "US Stocks",
        "US stock holdings will appear here once an "
        "international broker statement importer is added.")),
)


class HoldingsHubPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        # ---------------- Tab bar ---------------- #

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

        # ---------------- Content ---------------- #

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        self.current_tab = None
        self.current_page = None
        self.show_tab(TABS[0][0])  # always opens on Stocks

    # ---------------- Tab switching ---------------- #

    def show_tab(self, name):
        factory = dict(TABS).get(name)
        if factory is None:
            return
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page = factory(self.content)
        self.current_tab = name

        for tab_name, btn in self.tab_buttons.items():
            btn.configure(
                fg_color=ACCENT if tab_name == name else "transparent",
                text_color=SIDEBAR if tab_name == name else TEXT,
                hover_color=BORDER if tab_name != name else ACCENT,
            )
