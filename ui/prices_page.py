"""Prices page: manual price entry plus consent-gated price fetching.

Internet rule: every network fetch asks for permission with a dialog
EVERY time it runs; declining does zero network activity (the fetchers
enforce this too - the dialog is only the first of two gates).

The "Fetch prices" button tries NSE first. Whatever NSE could not fetch
(mutual-fund schemes excluded - they are not exchange-listed) gets a
second, separate consent dialog and a retry against Yahoo Finance.
"""

import tkinter.messagebox

import customtkinter as ctk

from database.manager import get_holdings, get_prices, set_price
from market_data.nse import ConsentRequired, fetch_nse_prices
from market_data.yahoo import YahooFetchError, fetch_yahoo_prices
from ui.formatting import format_quantity, format_rupees
from ui.theme import *


class PricesPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        self._entries = {}

        ctk.CTkLabel(
            self,
            text="Prices",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            self,
            text="Enter the latest price per holding. Prices value the "
                 "Market Value and P&L cards everywhere in the app.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack()

        # ---------------- Actions ---------------- #

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(pady=14)

        ctk.CTkButton(
            actions,
            text="Save prices",
            width=160,
            command=self.save_prices,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            actions,
            text="Fetch prices",
            width=160,
            fg_color=WARNING,
            hover_color="#C79100",
            text_color="#1E1E1E",
            command=self.fetch_from_nse,
        ).pack(side="left", padx=8)

        # ---------------- Price rows ---------------- #

        self.rows_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=BACKGROUND,
            width=980,
            height=440,
        )
        self.rows_frame.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

        self._build_rows()

    # ---------------- Rows ---------------- #

    def _build_rows(self):
        """One editable row per holding, prefilled from the prices table."""

        for widget in self.rows_frame.winfo_children():
            widget.destroy()
        self._entries.clear()

        stored = {row["symbol"]: row["price"] for row in get_prices()}

        header = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        for column, width in (
            ("Symbol", 300), ("Qty", 90), ("Avg", 120),
            ("Mkt value", 140), ("Price", 140), ("", 90),
        ):
            ctk.CTkLabel(
                header,
                text=column,
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
                width=width,
                anchor="w" if column in ("Symbol", "") else "e",
            ).pack(side="left", padx=6)

        holdings = get_holdings()
        if not holdings:
            ctk.CTkLabel(
                self.rows_frame,
                text="No holdings yet - import a broker file first.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(pady=20)
            return

        for row in holdings:
            line = ctk.CTkFrame(self.rows_frame, fg_color=CARD, corner_radius=6)
            line.pack(fill="x", pady=3)

            ctk.CTkLabel(
                line, text=row["symbol"], font=BODY_FONT, text_color=TEXT,
                width=300, anchor="w",
            ).pack(side="left", padx=6)
            ctk.CTkLabel(
                line, text=format_quantity(row["quantity"]), font=BODY_FONT,
                text_color=TEXT, width=90, anchor="e",
            ).pack(side="left", padx=6)
            ctk.CTkLabel(
                line, text=format_rupees(row["average_price"]), font=BODY_FONT,
                text_color=TEXT_SECONDARY, width=120, anchor="e",
            ).pack(side="left", padx=6)
            ctk.CTkLabel(
                line, text=format_rupees(row["market_value"]), font=BODY_FONT,
                text_color=TEXT, width=140, anchor="e",
            ).pack(side="left", padx=6)

            entry = ctk.CTkEntry(line, width=130, placeholder_text="price")
            entry.pack(side="left", padx=6)
            if row["symbol"] in stored:
                entry.insert(0, f"{stored[row['symbol']]:g}")
            self._entries[row["symbol"]] = entry

            source = "NSE" if self._is_nse_priced(row["symbol"]) else ""
            ctk.CTkLabel(
                line, text=source, font=SMALL_FONT,
                text_color=TEXT_SECONDARY, width=90,
            ).pack(side="left", padx=6)

    @staticmethod
    def _is_nse_priced(symbol):
        for row in get_prices():
            if row["symbol"] == symbol and row.get("source") == "NSE":
                return True
        return False

    # ---------------- Actions ---------------- #

    def save_prices(self):
        """Store every non-empty price field; report what was saved."""

        saved = 0
        errors = []
        for symbol, entry in self._entries.items():
            text = entry.get().strip()
            if not text:
                continue
            try:
                price = float(text)
            except ValueError:
                errors.append(f"{symbol}: '{text}' is not a number")
                continue
            if price <= 0:
                errors.append(f"{symbol}: price must be positive")
                continue
            set_price(symbol, price, source="manual")
            saved += 1

        self._build_rows()  # refresh market values from the new prices

        lines = [f"Saved {saved} price(s)."]
        lines.extend(errors)
        self._flash("\n".join(lines))

    def fetch_from_nse(self):
        """Ask permission EVERY time, then fetch quotes for all holdings.

        NSE first; whatever it could not fetch (excluding mutual-fund
        schemes, which are never listed) gets a second, separate consent
        dialog and a retry against Yahoo Finance.
        """

        symbols = sorted(self._entries)
        if not symbols:
            self._flash("No holdings to price.", error=True)
            return

        # ---- Consent gate (project rule: ask before every fetch) ---- #
        granted = tkinter.messagebox.askyesno(
            "Internet permission required",
            "PortfolioX is about to use the internet to fetch live prices "
            f"for {len(symbols)} symbol(s) from nseindia.com.\n\n"
            "Allow this fetch now?",
        )
        if not granted:
            self._flash("Fetch cancelled - no internet access was used.")
            return

        try:
            result = fetch_nse_prices(symbols, lambda: True)
        except ConsentRequired:
            self._flash("Fetch refused - no internet access was used.", error=True)
            return
        except Exception as error:
            self._flash(f"Fetch failed: {error}", error=True)
            return

        source = "NSE"
        failures = dict(result["failures"])

        # ---- Yahoo fallback: one more consent, then retry the misses ---- #
        # Mutual-fund schemes are never listed on an exchange; their
        # failure is the expected, friendly kind and must not trigger
        # a pointless second fetch.
        retry = [
            symbol for symbol, reason in result["failures"].items()
            if not reason.startswith("mutual fund")
        ]
        if retry:
            yahoo_granted = tkinter.messagebox.askyesno(
                "Internet permission required",
                f"NSE could not fetch {len(retry)} symbol(s).\n\n"
                "PortfolioX can try Yahoo Finance for them instead "
                "(one more internet request set).\n\n"
                "Try Yahoo Finance now?",
            )
            if yahoo_granted:
                try:
                    yahoo_result = fetch_yahoo_prices(retry, lambda: True)
                except YahooFetchError as error:
                    self._flash(f"Yahoo fetch refused: {error}", error=True)
                    return
                except Exception as error:
                    self._flash(f"Yahoo fetch failed: {error}", error=True)
                    return

                for symbol, price in yahoo_result["prices"].items():
                    set_price(symbol, price, source="Yahoo")
                source = "NSE + Yahoo"
                for symbol, reason in yahoo_result["failures"].items():
                    failures[symbol] = reason
                for symbol in yahoo_result["prices"]:
                    failures.pop(symbol, None)

        for symbol, price in result["prices"].items():
            set_price(symbol, price, source="NSE")

        self._build_rows()

        lines = [f"Fetched {len(result['prices'])} price(s) from {source}."]
        if failures:
            lines.append("Not fetched:")
            lines.extend(
                f"  {symbol}: {reason}" for symbol, reason in failures.items()
            )
        self._flash("\n".join(lines))

    def _flash(self, text, error=False):
        """Transient status line above the rows."""

        if getattr(self, "_status", None) is not None:
            self._status.destroy()
        self._status = ctk.CTkLabel(
            self,
            text=text,
            font=SMALL_FONT,
            text_color=ERROR if error else SUCCESS,
        )
        self._status.pack(pady=(0, 6))
