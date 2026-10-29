"""Holdings page: the stocks side of the holdings cache as a table.

Mutual fund and ETF positions are picked out by name heuristics and
shown on the hub's Mutual Funds tab instead (see mutual_funds_page);
this page keeps plain stocks and F&O contracts. It also hosts
hand-entered positions: manual holdings live in their own table and
are merged into the rebuilt cache, so they show up in the main table
alongside transaction-derived positions.
"""

import customtkinter as ctk

from calculations.allocation import split_holdings_by_class
from database.manager import (
    add_manual_holding,
    delete_manual_holding,
    get_accounts,
    get_holdings,
    get_manual_holdings,
    rebuild_holdings,
)
from ui.formatting import format_quantity, format_rupees
from ui.theme import *

_COLUMNS = (
    ("Symbol", 320, "w"),
    ("Quantity", 140, "e"),
    ("Avg Price", 160, "e"),
    ("Invested", 200, "e"),
)


class HoldingsPage(ctk.CTkFrame):

    def __init__(self, parent, account_id=None):
        super().__init__(parent, fg_color=BACKGROUND)
        self._account_id = account_id  # None = every account
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._status = None

        ctk.CTkLabel(
            self,
            text="Stocks",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        summary = ctk.CTkLabel(
            self,
            text=self._summary_line(),
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        )
        summary.pack(pady=(0, 16))

        self._table()
        self._manual_form()
        self._manual_list()

    def _summary_line(self):
        stocks, _ = split_holdings_by_class(get_holdings(self._account_id))
        invested = sum(row["invested_amount"] for row in stocks)
        return (
            f"{len(stocks)} stock positions - total invested "
            f"{format_rupees(invested)} (market value arrives with live prices)"
        )

    def _table(self):
        """Scrollable stocks table, or a friendly empty state."""

        stocks, _ = split_holdings_by_class(get_holdings(self._account_id))

        if not stocks:
            ctk.CTkLabel(
                self,
                text="No stock holdings yet - import a broker file or add one manually below.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=10)
            return

        header = ctk.CTkFrame(self, fg_color="transparent")
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

        body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND, height=220)
        body.pack(fill="both", expand=True, padx=PADDING, pady=(4, PADDING))

        for row in stocks:
            line = ctk.CTkFrame(body, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=2)
            for value, (_, width, anchor) in zip(
                (
                    row["symbol"],
                    format_quantity(row["quantity"]),
                    format_rupees(row["average_price"]),
                    format_rupees(row["invested_amount"]),
                ),
                _COLUMNS,
            ):
                ctk.CTkLabel(
                    line,
                    text=value,
                    font=BODY_FONT,
                    text_color=TEXT,
                    width=width,
                    anchor=anchor,
                ).pack(side="left", padx=8)

    # ------------------------------------------------- manual holdings #

    def _manual_form(self):
        """Card with the add-holding-manually form."""

        form = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        form.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        ctk.CTkLabel(
            form,
            text="Add holding manually",
            font=HEADING_FONT,
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        self.symbol_entry = ctk.CTkEntry(row, width=180, placeholder_text="Symbol (e.g. RELIANCE)")
        self.symbol_entry.pack(side="left", padx=(0, 10))

        self.quantity_entry = ctk.CTkEntry(row, width=120, placeholder_text="Quantity")
        self.quantity_entry.pack(side="left", padx=(0, 10))

        self.price_entry = ctk.CTkEntry(row, width=150, placeholder_text="Avg price (₹)")
        self.price_entry.pack(side="left", padx=(0, 10))

        accounts = get_accounts()
        self._account_ids = [account["id"] for account in accounts]
        self.account_menu = ctk.CTkOptionMenu(
            row,
            values=[account["name"] for account in accounts] or ["(no accounts)"],
            width=170,
        )
        if accounts:
            self.account_menu.set(accounts[0]["name"])
        self.account_menu.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            row,
            text="Add holding",
            width=130,
            command=self.add_manual_clicked,
        ).pack(side="left")

    def _manual_list(self):
        """Existing manual entries with delete buttons."""

        manual = get_manual_holdings()
        if not manual:
            return

        section = ctk.CTkFrame(self, fg_color="transparent")
        section.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        ctk.CTkLabel(
            section,
            text="Manual entries (removed from the table when deleted)",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 4))

        for entry in manual:
            line = ctk.CTkFrame(section, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(
                line, text=entry["account_name"], font=SMALL_FONT,
                text_color=TEXT_SECONDARY, width=160, anchor="w",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=entry["symbol"], font=BODY_FONT,
                text_color=TEXT, width=180, anchor="w",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=format_quantity(entry["quantity"]), font=BODY_FONT,
                text_color=TEXT, width=110, anchor="e",
            ).pack(side="left", padx=8)
            ctk.CTkLabel(
                line, text=f"@ {format_rupees(entry['average_price'])}",
                font=BODY_FONT, text_color=TEXT, width=130, anchor="e",
            ).pack(side="left", padx=8)
            ctk.CTkButton(
                line, text="Delete", width=70, height=24,
                fg_color="transparent", border_width=1,
                text_color=ERROR,
                command=lambda entry_id=entry["id"]: self.delete_manual_clicked(entry_id),
            ).pack(side="left", padx=(0, 8))

    def _selected_account_id(self):
        names = {
            account["name"]: account["id"]
            for account in get_accounts()
        }
        return names.get(self.account_menu.get())

    def add_manual_clicked(self):
        symbol = self.symbol_entry.get().strip()
        quantity_text = self.quantity_entry.get().strip()
        price_text = self.price_entry.get().strip().replace(",", "")

        account_id = self._selected_account_id()
        if account_id is None:
            self._flash("Select an account first.", error=True)
            return

        try:
            quantity = float(quantity_text)
            average_price = float(price_text)
            add_manual_holding(account_id, symbol, quantity, average_price)
        except ValueError as error:
            self._flash(str(error), error=True)
            return

        rebuild_holdings()
        self._build()
        self._flash(f"Added {quantity:g} {symbol.upper()} manually.")

    def delete_manual_clicked(self, manual_id):
        delete_manual_holding(manual_id)
        rebuild_holdings()
        self._build()

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
