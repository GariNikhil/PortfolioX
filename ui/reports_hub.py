"""Reports hub: tab bar over the report sub-pages.

One sidebar entry ("Reports") opens this hub; the tab bar at the top
switches the content between reports. Always opens on Demat Report.
"""

import customtkinter as ctk

from ui.balance_statement_page import BalanceStatementPage
from ui.coming_soon_page import ComingSoonPage
from ui.dividend_report_page import DividendReportPage
from ui.import_report_page import ImportReportPage
from ui.reports_page import ReportsPage
from ui.theme import *

TABS = (
    ("Demat Report", lambda parent: ReportsPage(parent)),
    ("Balance Statement", lambda parent: BalanceStatementPage(parent)),
    ("Contract Note", lambda parent: ImportReportPage(parent)),
    ("Dividend Report", lambda parent: DividendReportPage(parent)),
    ("US Stocks Report", lambda parent: ComingSoonPage(
        parent, "US Stocks Report",
        "A US stocks report will arrive together with the US "
        "stocks importer.")),
)


class ReportsHubPage(ctk.CTkFrame):

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
        self.show_tab(TABS[0][0])  # always opens on Demat Report

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
