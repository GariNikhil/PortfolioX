import customtkinter as ctk

from ui.accounts_page import AccountsPage
from ui.coming_soon_page import ComingSoonPage
from ui.dashboard import DashboardPage
from ui.dividend_report_page import DividendReportPage
from ui.dividends_page import DividendsPage
from ui.holdings_page import HoldingsPage
from ui.import_page import ImportPage
from ui.import_report_page import ImportReportPage
from ui.learn_page import LearnPage
from ui.prices_page import PricesPage
from ui.reports_page import ReportsPage
from ui.settings_page import SettingsPage
from ui.tax_page import TaxPage
from ui.theme import *
from ui.transactions_page import TransactionsPage
from ui.vault_page import VaultPage


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

        # Grouped menu: (section label or None, [(page name, factory)]).
        # Factories take the parent frame, so pages needing constructor
        # arguments are wrapped in lambdas. Grouped sections render as
        # collapsible drop-lists (collapsed by default).
        self.menu = (
            (None, (
                ("Dashboard", DashboardPage),
                ("Accounts", AccountsPage),
                ("Import", ImportPage),
            )),
            ("HOLDINGS", (
                ("Stocks", HoldingsPage),
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
            )),
            (None, (
                ("Prices", PricesPage),
                ("Transactions", TransactionsPage),
            )),
            ("REPORTS", (
                ("Demat Report", ReportsPage),
                ("Balance Statement", lambda parent: ComingSoonPage(
                    parent, "Balance Statement",
                    "A balance statement (funds + securities value) will be "
                    "generated from contract notes and holdings.")),
                ("Contract Note", ImportReportPage),
                ("Dividend Report", DividendReportPage),
                ("US Stocks Report", lambda parent: ComingSoonPage(
                    parent, "US Stocks Report",
                    "A US stocks report will arrive together with the US "
                    "stocks importer.")),
            )),
            (None, (
                ("Dividends", DividendsPage),
                ("Tax", TaxPage),
                ("Pass Vault", VaultPage),
                ("Learn", LearnPage),
                ("Settings", SettingsPage),
            )),
        )

        self.buttons = {}
        self.sections = {}  # label -> {"header", "body", "open", "pages"}

        # Grid (not pack) inside the scrollable frame: hiding a section
        # body with grid_remove keeps every other row in place.
        nav = ctk.CTkScrollableFrame(
            self.sidebar,
            width=SIDEBAR_WIDTH - 20,
            fg_color=SIDEBAR,
        )
        nav.pack(fill="both", expand=True, padx=(0, 4), pady=(0, 8))
        nav.grid_columnconfigure(0, weight=1)

        row = 0

        for label, items in self.menu:

            if label is None:
                for name, factory in items:
                    btn = ctk.CTkButton(
                        nav,
                        text=name,
                        width=180,
                        height=42,
                        fg_color="transparent",
                        text_color=TEXT,
                        hover_color=BORDER,
                        command=lambda x=name: self.show_page(x),
                    )
                    btn.grid(row=row, column=0, sticky="ew", padx=6, pady=2)
                    row += 1
                    self.buttons[name] = btn
                continue

            # Collapsible section: header toggles the body frame.
            header = ctk.CTkButton(
                nav,
                text=f"▸  {label}",
                width=180,
                height=32,
                font=(FONT_FAMILY, 12, "bold"),
                anchor="w",
                fg_color="transparent",
                text_color=TEXT_SECONDARY,
                hover_color=BORDER,
                command=lambda l=label: self.toggle_section(l),
            )
            header.grid(row=row, column=0, sticky="ew", padx=6, pady=(8, 2))
            row += 1

            body = ctk.CTkFrame(nav, fg_color="transparent")
            for name, factory in items:
                btn = ctk.CTkButton(
                    body,
                    text="    " + name,
                    width=180,
                    height=38,
                    font=SMALL_FONT,
                    anchor="w",
                    fg_color="transparent",
                    text_color=TEXT,
                    hover_color=BORDER,
                    command=lambda x=name: self.show_page(x),
                )
                btn.pack(pady=1, padx=(14, 0))
                self.buttons[name] = btn

            # Collapsed by default: grid_remove-friendly grid() then forget.
            body.grid(row=row, column=0, sticky="ew")
            row += 1
            body.grid_remove()

            self.sections[label] = {
                "header": header,
                "body": body,
                "open": False,
                "pages": [name for name, _ in items],
            }

        self.current_page = None

        self.pages = {
            name: factory
            for _, items in self.menu
            for name, factory in items
        }

        self.show_page("Dashboard")

    # ---------------- Section toggling ---------------- #

    def toggle_section(self, label):
        section = self.sections[label]
        section["open"] = not section["open"]
        self._apply_section(label)

    def _apply_section(self, label):
        section = self.sections[label]
        arrow = "▾" if section["open"] else "▸"
        section["header"].configure(text=f"{arrow}  {label}")
        if section["open"]:
            section["body"].grid()
        else:
            section["body"].grid_remove()

    def _ensure_section_open(self, page):
        """Open the section containing page, so its highlight is visible."""

        for label, section in self.sections.items():
            if page in section["pages"] and not section["open"]:
                section["open"] = True
                self._apply_section(label)

    # ---------------- Page Navigation ---------------- #

    def show_page(self, page):
        factory = self.pages.get(page, DashboardPage)
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page = factory(self.content)
        self._ensure_section_open(page)

        # Highlight the active navigation button.
        for name, btn in self.buttons.items():
            btn.configure(
                fg_color=ACCENT if name == page else "transparent",
                text_color=SIDEBAR if name == page else TEXT,
                hover_color=BORDER if name != page else ACCENT,
            )
