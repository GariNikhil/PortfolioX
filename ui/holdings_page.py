import customtkinter as ctk

from ui.theme import *


class HoldingsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="Holdings",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 12))

        ctk.CTkLabel(
            self,
            text="Your portfolio holdings will appear here.",
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=8)
