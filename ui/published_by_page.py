"""Published by page: read-only publisher details, shown inside Settings.

The values live in ``ui.published_by_content`` rather than in the
database, so the page has nothing to save and nothing to validate. Each
field is skipped when it was left blank, which is why a name alone still
produces a complete-looking card.

Profile links open in the default browser, and only when clicked; the
page never fetches anything by itself.
"""

import webbrowser

import customtkinter as ctk

from ui.published_by_content import profile_rows
from ui.theme import *

# Width at which a long bio wraps. The content area is about 900 px at the
# minimum window size, so this leaves the card room to breathe.
BIO_WRAP = 700


class PublishedByPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="👤 Published by",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Who publishes PortfolioX. The details live in the code, "
                 "not in the database.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._profile_card()
        self._app_footer()

    # ---------------- Profile ---------------- #

    def _profile_card(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        card.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=PADDING, pady=PADDING)

        rows = profile_rows()
        if not rows:
            ctk.CTkLabel(
                body,
                text="No details filled in yet.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
                anchor="w",
            ).pack(anchor="w")
            return

        for position, (kind, value) in enumerate(rows):
            top = 0 if position == 0 else 16
            if kind == "name":
                self._show_name(body, value, top)
            elif kind == "bio":
                self._show_bio(body, value, top)
            elif kind == "email":
                self._show_email(body, value, top)
            else:
                self._show_links(body, value, top)

    def _show_name(self, parent, value, top):
        ctk.CTkLabel(
            parent,
            text=value,
            font=HEADING_FONT,
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w", pady=(top, 0))

    def _show_bio(self, parent, value, top):
        ctk.CTkLabel(
            parent,
            text=value,
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
            justify="left",
            wraplength=BIO_WRAP,
        ).pack(anchor="w", pady=(top, 0))

    def _show_email(self, parent, value, top):
        ctk.CTkLabel(
            parent,
            text="EMAIL",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(anchor="w", pady=(top, 0))

        ctk.CTkLabel(
            parent,
            text=value,
            font=BODY_FONT,
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")

    def _show_links(self, parent, links, top):
        ctk.CTkLabel(
            parent,
            text="LINKS",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(anchor="w", pady=(top, 6))

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(anchor="w")

        for label, url in links:
            ctk.CTkButton(
                row,
                text=label,
                width=110,
                height=30,
                font=SMALL_FONT,
                corner_radius=15,
                fg_color="transparent",
                border_width=1,
                border_color=BORDER,
                text_color=TEXT,
                hover_color=BORDER,
                command=lambda address=url: webbrowser.open(address),
            ).pack(side="left", padx=(0, 8))

    # ---------------- App ---------------- #

    def _app_footer(self):
        ctk.CTkLabel(
            self,
            text="PortfolioX - a local-first portfolio ledger. All data "
                 "stays on this computer.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=PADDING)
