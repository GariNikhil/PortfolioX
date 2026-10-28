import customtkinter as ctk

from ui.accounts_page import AccountsPage
from ui.dashboard import DashboardPage
from ui.dividends_page import DividendsPage
from ui.holdings_hub import HoldingsHubPage
from ui.import_page import ImportPage
from ui.learn_page import LearnPage
from ui.prices_page import PricesPage
from ui.settings_hub import SettingsHubPage
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

        title.pack(pady=(24, 12))

        # ---------------- Navigation ---------------- #

        # Flat list; Holdings, Reports and Settings are hub pages whose
        # sub-pages live behind a tab bar at the top of the content area.
        self.menu = (
            ("Dashboard", DashboardPage),
            ("Accounts", AccountsPage),
            ("Import", ImportPage),
            ("Holdings", HoldingsHubPage),
            ("Prices", PricesPage),
            ("Transactions", TransactionsPage),
            ("Dividends", DividendsPage),
            ("Learn", LearnPage),
            ("Settings", SettingsHubPage),
        )

        self.buttons = {}

        nav = ctk.CTkScrollableFrame(
            self.sidebar,
            width=SIDEBAR_WIDTH - 20,
            fg_color=SIDEBAR,
        )
        nav.pack(fill="both", expand=True, padx=(0, 4), pady=(0, 8))

        for name, factory in self.menu:
            btn = ctk.CTkButton(
                nav,
                text=name,
                width=180,
                height=40,
                fg_color="transparent",
                text_color=TEXT,
                hover_color=BORDER,
                command=lambda x=name: self.show_page(x),
            )
            btn.pack(pady=3, padx=6)
            self.buttons[name] = btn

        self.current_page = None

        self.pages = dict(self.menu)

        self.show_page("Dashboard")

    # ---------------- Page Navigation ---------------- #

    def show_page(self, page):
        factory = self.pages.get(page, DashboardPage)
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page = factory(self.content)

        # Highlight the active navigation button.
        for name, btn in self.buttons.items():
            btn.configure(
                fg_color=ACCENT if name == page else "transparent",
                text_color=SIDEBAR if name == page else TEXT,
                hover_color=BORDER if name != page else ACCENT,
            )
