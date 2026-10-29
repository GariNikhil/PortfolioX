"""Banking page: imported bank-statement transactions, newest first.

Bank transactions live in their own table (bank_transactions), so this
page is separate from the brokerage Transactions page. Pick a bank
account to see its statement lines with the running balance; the
summary line shows the latest balance and the money in / out totals.
"""

import customtkinter as ctk

from database.manager import (
    count_bank_transactions,
    get_accounts,
    get_bank_transactions,
)
from ui.formatting import format_rupees
from ui.theme import *

_COLUMNS = (
    ("Date", 100, "w"),
    ("Description", 420, "w"),
    ("Debit", 110, "e"),
    ("Credit", 110, "e"),
    ("Balance", 150, "e"),
)

_ROWS_SHOWN = 600


class BankingPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="Banking",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        self.accounts = [
            account for account in self._bank_accounts()
        ]

        picker = ctk.CTkFrame(self, fg_color="transparent")
        picker.pack(pady=(0, 8))
        ctk.CTkLabel(
            picker,
            text="Account:",
            font=BODY_FONT,
            text_color=TEXT,
        ).pack(side="left", padx=(0, 8))

        names = [account["name"] for account in self.accounts]
        if names:
            self.account_menu = ctk.CTkOptionMenu(
                picker,
                values=names,
                width=240,
                command=lambda _choice: self._refresh(),
            )
            self.account_menu.set(names[0])
            self.account_menu.pack(side="left")
        else:
            ctk.CTkLabel(
                picker,
                text="no bank accounts with imported statements yet",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(side="left")

        # Rebuilt on every account switch.
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        if names:
            self._refresh()
        else:
            ctk.CTkLabel(
                self.content,
                text="No bank statements imported yet.\n"
                     "Use Import -> 'Axis Bank statement (PDF)' or\n"
                     "'PNB mPassbook statement (PDF)'.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
                justify="center",
            ).pack(pady=40)

    @staticmethod
    def _bank_accounts():
        """Accounts that have imported bank transactions, in menu order."""

        return [
            account for account in get_accounts()
            if count_bank_transactions(account_id=account["id"]) > 0
        ]

    def _refresh(self):
        """Rebuild the summary + table for the selected account."""

        for child in self.content.winfo_children():
            child.destroy()

        name = self.account_menu.get()
        account = next(
            (entry for entry in self.accounts if entry["name"] == name),
            None,
        )
        if account is None:
            return

        transactions = list(reversed(
            get_bank_transactions(account_id=account["id"]),
        ))

        ctk.CTkLabel(
            self.content,
            text=self._summary_line(transactions),
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._table(transactions)

    @staticmethod
    def _summary_line(transactions):
        if not transactions:
            return "No transactions stored for this account yet."

        total_out = sum(-row["amount"] for row in transactions
                        if row["amount"] < 0)
        total_in = sum(row["amount"] for row in transactions
                       if row["amount"] > 0)
        balance = transactions[0]["balance"]
        return (
            f"{len(transactions)} transactions - in {format_rupees(total_in)}, "
            f"out {format_rupees(total_out)}, balance {format_rupees(balance)}"
        )

    def _table(self, transactions):
        """Scrollable statement list (capped for UI responsiveness)."""

        if not transactions:
            ctk.CTkLabel(
                self.content,
                text="No transactions stored for this account yet.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=30)
            return

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=PADDING)
        for name, width, anchor in _COLUMNS:
            ctk.CTkLabel(
                header,
                text=name,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
                width=width,
                anchor=anchor,
            ).pack(side="left", padx=8)

        body = ctk.CTkScrollableFrame(self.content, fg_color=BACKGROUND)
        body.pack(fill="both", expand=True, padx=PADDING, pady=(4, PADDING))

        for row in transactions[:_ROWS_SHOWN]:
            amount = row["amount"]
            line = ctk.CTkFrame(body, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=1)
            values = (
                row["txn_date"],
                row["description"],
                format_rupees(-amount) if amount < 0 else "",
                format_rupees(amount) if amount > 0 else "",
                format_rupees(row["balance"]),
            )
            for value, (_, width, anchor) in zip(values, _COLUMNS):
                ctk.CTkLabel(
                    line,
                    text=value,
                    font=BODY_FONT,
                    text_color=SUCCESS if amount > 0 else TEXT,
                    width=width,
                    anchor=anchor,
                ).pack(side="left", padx=8)

        if len(transactions) > _ROWS_SHOWN:
            ctk.CTkLabel(
                body,
                text=f"Showing the {_ROWS_SHOWN} most recent of "
                     f"{len(transactions)} transactions.",
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=8)
