"""Accounts page: list accounts and add more broker / personal accounts.

The user's model: a main broker account, a main personal account, and the
option to add more of either kind. Transactions and holdings carry an
account_id; rows from before accounts existed stay "Unassigned".
"""

import customtkinter as ctk

from database.manager import (
    UNASSIGNED,
    add_account,
    get_accounts,
    get_portfolio_summary,
)
from ui.formatting import format_rupees
from ui.theme import *


class AccountsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="Accounts",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(30, 16))

        # ---------------- Add form ---------------- #

        form = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        form.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        ctk.CTkLabel(
            form,
            text="Add account",
            font=HEADING_FONT,
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        self.name_entry = ctk.CTkEntry(row, width=280, placeholder_text="Account name")
        self.name_entry.pack(side="left", padx=(0, 10))

        self.kind_menu = ctk.CTkOptionMenu(row, values=["Broker", "Personal"], width=140)
        self.kind_menu.set("Broker")
        self.kind_menu.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            row,
            text="Add account",
            width=130,
            command=self.add_account_clicked,
        ).pack(side="left")

        # ---------------- Account list ---------------- #

        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=PADDING)

        self._build_list()

    def _build_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        header = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        for column, width, anchor in (
            ("Name", 300, "w"), ("Kind", 130, "w"),
            ("Transactions", 150, "e"), ("Invested", 180, "e"),
        ):
            ctk.CTkLabel(
                header,
                text=column,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
                width=width,
                anchor=anchor,
            ).pack(side="left", padx=8)

        accounts = get_accounts()
        if not accounts:
            ctk.CTkLabel(
                self.list_frame,
                text="No accounts.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=16)

        for account in accounts:
            self._account_row(account)

        # Unassigned bucket: pre-account rows waiting to be tagged.
        unassigned = get_portfolio_summary(account_id=UNASSIGNED)
        if unassigned["total_transactions"]:
            line = ctk.CTkFrame(self.list_frame, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=3)
            ctk.CTkLabel(
                line, text="Unassigned (imported before accounts)",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
                width=300, anchor="w",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text="-", font=BODY_FONT, text_color=TEXT_SECONDARY,
                width=130, anchor="w",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=str(unassigned["total_transactions"]),
                font=BODY_FONT, text_color=TEXT,
                width=150, anchor="e",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=format_rupees(unassigned["total_invested"]),
                font=BODY_FONT, text_color=TEXT,
                width=180, anchor="e",
            ).pack(side="left", padx=8)

    def _account_row(self, account):
        line = ctk.CTkFrame(self.list_frame, fg_color=CARD, corner_radius=6)
        line.pack(fill="x", pady=3)

        name = account["name"]
        badges = []
        if account["is_main"]:
            badges.append("MAIN")
        badge_text = f"  [{' / '.join(badges)}]" if badges else ""

        ctk.CTkLabel(
            line, text=f"{name}{badge_text}", font=BODY_FONT, text_color=TEXT,
            width=300, anchor="w",
        ).pack(side="left", padx=8)
        ctk.CTkLabel(
            line, text=account["kind"], font=SMALL_FONT,
            text_color=SUCCESS if account["kind"] == "BROKER" else WARNING,
            width=130, anchor="w",
        ).pack(side="left", padx=8)
        ctk.CTkLabel(
            line, text=str(account["transaction_count"]),
            font=BODY_FONT, text_color=TEXT,
            width=150, anchor="e",
        ).pack(side="left", padx=8)

        summary = get_portfolio_summary(account_id=account["id"])
        ctk.CTkLabel(
            line, text=format_rupees(summary["total_invested"]),
            font=BODY_FONT, text_color=TEXT,
            width=180, anchor="e",
        ).pack(side="left", padx=8)

    def add_account_clicked(self):
        name = self.name_entry.get().strip()
        kind = self.kind_menu.get().upper()

        try:
            add_account(name, kind)
        except ValueError as error:
            self._flash(str(error), error=True)
            return

        self.name_entry.delete(0, "end")
        self._build_list()
        self._flash(f"Added {kind.lower()} account '{name}'.")

    def _flash(self, text, error=False):
        if getattr(self, "_status", None) is not None:
            self._status.destroy()
        self._status = ctk.CTkLabel(
            self,
            text=text,
            font=SMALL_FONT,
            text_color=ERROR if error else SUCCESS,
        )
        self._status.pack(pady=(6, 0))
