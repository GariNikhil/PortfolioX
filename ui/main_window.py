import customtkinter as ctk

from ui.dashboard import DashboardPage
from ui.holdings_page import HoldingsPage
from ui.import_page import ImportPage
from ui.reports_page import ReportsPage
from ui.settings_page import SettingsPage
from ui.theme import *
from ui.transactions_page import TransactionsPage


class PortfolioX(ctk.CTk):

    def __init__(self):
        super().__init__()

        # ---------------- Window ---------------- #

        self.title("PortfolioX")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(1200, 700)

        # ---------------- Layout ---------------- #

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- Sidebar ---------------- #

        self.sidebar = ctk.CTkFrame(
            self,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=SIDEBAR
        )

        self.sidebar.grid(row=0, column=0, sticky="ns")

        # ---------------- Content ---------------- #

        self.content = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=BACKGROUND
        )

        self.content.grid(row=0, column=1, sticky="nsew")

        # ---------------- Title ---------------- #

        title = ctk.CTkLabel(
            self.sidebar,
            text="📊 PortfolioX",
            font=TITLE_FONT,
            text_color=TEXT
        )

        title.pack(pady=30)

        # ---------------- Navigation ---------------- #

        self.buttons = {}

        menu = [
            "Dashboard",
            "Import",
            "Holdings",
            "Transactions",
            "Reports",
            "Settings"
        ]

        for item in menu:

            btn = ctk.CTkButton(
                self.sidebar,
                text=item,
                width=180,
                height=42,
                command=lambda x=item: self.show_page(x)
            )

            btn.pack(pady=8)

            self.buttons[item] = btn

        self.current_page = None

        self.pages = {
            "Dashboard": DashboardPage,
            "Import": ImportPage,
            "Holdings": HoldingsPage,
            "Transactions": TransactionsPage,
            "Reports": ReportsPage,
            "Settings": SettingsPage,
        }

        self.show_page("Dashboard")

    # ---------------- Page Navigation ---------------- #

    def show_page(self, page):
        page_class = self.pages.get(page, DashboardPage)
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page = page_class(self.content)