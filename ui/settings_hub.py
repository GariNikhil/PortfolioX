"""Settings hub: tab bar over Reports, Tax, Pass Vault, General and About.

One sidebar entry ("Settings") consolidates the auxiliary pages. The
Reports tab embeds the reports hub (with its own sub-tab bar); General
holds the original settings content (vault health, database location);
About me is the read-only profile page. Always opens on Reports.
"""

import customtkinter as ctk

from ui.about_page import AboutPage
from ui.reports_hub import ReportsHubPage
from ui.settings_page import SettingsPage
from ui.tax_page import TaxPage
from ui.theme import *
from ui.vault_page import VaultPage

TABS = (
    ("Reports", lambda parent: ReportsHubPage(parent)),
    ("Tax", lambda parent: TaxPage(parent)),
    ("Pass Vault", lambda parent: VaultPage(parent)),
    ("General", lambda parent: SettingsPage(parent)),
    ("About", lambda parent: AboutPage(parent)),
)


class SettingsHubPage(ctk.CTkFrame):

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
        self.show_tab(TABS[0][0])  # always opens on Reports

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
