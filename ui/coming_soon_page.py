"""Shared empty-state page for asset classes and reports without data yet.

Each one states what will live here and how it arrives (its own importer
or report writer), so an empty section reads as a roadmap rather than a
broken feature.
"""

import customtkinter as ctk

from ui.theme import *


class ComingSoonPage(ctk.CTkFrame):

    def __init__(self, parent, title, message):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text=title,
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(120, 8))

        ctk.CTkLabel(
            self,
            text=message,
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
            justify="center",
        ).pack(padx=PADDING, pady=10)
