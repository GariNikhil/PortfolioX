import customtkinter as ctk

from ui.theme import *


class TransactionsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="Transactions",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 12))

        ctk.CTkLabel(
            self,
            text="Imported buy and sell transactions will appear here.",
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=8)
