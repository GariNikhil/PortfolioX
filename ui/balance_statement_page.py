"""Balance Statement page: funds overview plus the full import audit.

Two sections:

- Funds: every account with its kind and current balance, so the cash
  side of the portfolio is visible at a glance.
- Imported files: every import attempt from the audit table (bank
  statements included, no type filter) with its outcome, so it is easy
  to check whether a file was imported. Each row has a Remove option
  that deletes the file's imported data together with its audit entry.
"""

import customtkinter as ctk

from database.manager import (
    delete_import,
    get_accounts,
    get_import_row_counts,
    get_imports,
    rebuild_holdings,
)
from ui.formatting import format_rupees
from ui.theme import *

_TYPE_LABELS = {
    "GROWW_TRADEBOOK": "Tradebook",
    "CONTRACT_NOTE_PDF": "Contract note",
    "CONTRACT_NOTE_ORDERS": "CN orders",
    "ORDERS_XLSX": "Orders file",
    "IIFL_TRADE_LISTING": "IIFL trades",
    "STOCKSLEDGER_PORTFOLIO": "Ledger",
    "HOLDING_REPORT": "Stocks stmt",
    "MF_HOLDING_REPORT": "MF stmt",
    "AXIS_STATEMENT": "Axis stmt",
    "PNB_MPASSBOOK": "PNB stmt",
}


def _type_label(import_type):
    """Human name for an import type; unknown types pass through."""

    return _TYPE_LABELS.get(str(import_type or ""), str(import_type or ""))


def _counts_text(counts):
    """One line describing what a Remove would delete."""

    if not counts:
        return "no data rows are linked - only the audit entry is removed"
    parts = []
    if counts.get("transactions"):
        parts.append(f"{counts['transactions']} transaction(s)")
    if counts.get("bank_transactions"):
        parts.append(f"{counts['bank_transactions']} bank row(s)")
    if counts.get("manual_holdings"):
        parts.append(f"{counts['manual_holdings']} holding row(s)")
    return "removes " + ", ".join(parts)


def _clip(text, limit):
    """Keep table cells inside their fixed column width."""

    text = str(text or "")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _status_text(status):
    """Compact status: the detail after 'FAILED (...)' is audit noise."""

    upper = str(status or "").upper()
    for prefix in ("SUCCESS", "FAILED", "SKIPPED", "PENDING"):
        if upper.startswith(prefix):
            return prefix
    return _clip(status, 14)


class BalanceStatementPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._status = None
        self._scroll = None
        self._import_lines = {}  # import_id -> row frame (for tests/tools)

        ctk.CTkLabel(
            self,
            text="⚖ Balance Statement",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Account balances and every imported file with its outcome.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        # Funds on the left, the import list filling the rest: the file
        # list is the long one, so it gets the height.
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))
        self._funds(row)
        self._imports(row)

    # ------------------------------------------------------------- funds #

    def _funds(self, parent):
        """Narrow card listing every account with its kind and balance."""

        frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=8)
        frame.pack(side="left", fill="y", padx=(0, PADDING))

        accounts = get_accounts()
        ctk.CTkLabel(
            frame,
            text="Funds",
            font=HEADING_FONT,
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        if not accounts:
            ctk.CTkLabel(
                frame,
                text="No accounts yet.",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
            ).pack(padx=16, pady=(0, 12), anchor="w")
            return

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(0, 4))
        for text, width, anchor in (
            ("Account", 130, "w"), ("Kind", 55, "w"), ("Balance", 90, "e"),
        ):
            ctk.CTkLabel(header, text=text, width=width, anchor=anchor,
                         font=SMALL_FONT, text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=2)

        for account in accounts:
            line = ctk.CTkFrame(frame, fg_color="transparent")
            line.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(line, text=_clip(account["name"], 18), width=130,
                         anchor="w", font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=account["kind"] or "", width=55,
                         anchor="w", font=SMALL_FONT,
                         text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(
                line, width=90, anchor="e", font=BODY_FONT, text_color=TEXT,
                text=format_rupees(account["current_balance"]),
            ).pack(side="left", padx=2)

        ctk.CTkLabel(frame, text="").pack(pady=(0, 6))

    # ----------------------------------------------------------- imports #

    def _imports(self, parent):
        """Scrollable card listing every import with a Remove option."""

        frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=8)
        frame.pack(side="left", fill="both", expand=True)

        imports = get_imports()
        ctk.CTkLabel(
            frame,
            text="Imported files",
            font=HEADING_FONT,
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        if not imports:
            ctk.CTkLabel(
                frame,
                text="No files imported yet.",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
            ).pack(padx=16, pady=(0, 12), anchor="w")
            return

        success = sum(
            1 for row in imports
            if str(row["status"]).upper().startswith("SUCCESS")
        )
        ctk.CTkLabel(
            frame,
            text=f"{len(imports)} files · {success} imported · "
                 f"{len(imports) - success} failed/skipped",
            font=SMALL_FONT, text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(0, 6))

        body = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._scroll = body

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(0, 4))
        for text, width, anchor in (
            ("File", 190, "w"), ("Type", 105, "w"), ("Imported", 95, "w"),
            ("Status", 100, "w"), ("", 70, "e"),
        ):
            ctk.CTkLabel(header, text=text, width=width, anchor=anchor,
                         font=SMALL_FONT, text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=2)

        for row in imports:
            self._import_line(body, row)

    def _import_line(self, body, row):
        """One import row: details plus a Remove button."""

        line = ctk.CTkFrame(body, fg_color="transparent")
        line.pack(fill="x", padx=8, pady=2)
        self._import_lines[row["id"]] = line

        status = _status_text(row["status"])
        raw = str(row["status"] or "").upper()
        if raw.startswith("SUCCESS"):
            color = SUCCESS
        elif raw.startswith("FAILED"):
            color = ERROR
        else:
            color = WARNING

        ctk.CTkLabel(line, text=_clip(row["filename"], 21), width=190,
                     anchor="w", font=SMALL_FONT, text_color=TEXT
                     ).pack(side="left", padx=2)
        ctk.CTkLabel(line, text=_type_label(row["import_type"]), width=105,
                     anchor="w", font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).pack(side="left", padx=2)
        ctk.CTkLabel(line, text=str(row["imported_date"])[5:16], width=95,
                     anchor="w", font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).pack(side="left", padx=2)
        ctk.CTkLabel(line, text=status, width=100,
                     anchor="w", font=SMALL_FONT, text_color=color
                     ).pack(side="left", padx=2)
        ctk.CTkButton(
            line, text="Remove", width=90, height=24,
            fg_color="transparent", border_width=1,
            text_color=ERROR,
            command=lambda line=line, row=row: self._confirm_remove(line, row),
        ).pack(side="right", padx=(0, 8))

    def _confirm_remove(self, line, row):
        """Swap an import row for a delete confirmation with row counts."""

        for widget in line.winfo_children():
            widget.destroy()

        counts = get_import_row_counts(row["id"])
        ctk.CTkLabel(
            line,
            text=(f"Remove '{row['filename']}'? {_counts_text(counts)}."),
            font=SMALL_FONT,
            text_color=TEXT,
        ).pack(side="left", padx=(2, 8), fill="x", expand=True)

        def remove_clicked():
            delete_import(row["id"])
            rebuild_holdings()
            self._build()
            self._flash(f"Removed '{row['filename']}'.")

        ctk.CTkButton(
            line, text="Confirm", width=90, height=24,
            fg_color=ERROR, hover_color="#C62828",
            text_color=TEXT,
            command=remove_clicked,
        ).pack(side="right", padx=(0, 8))
        ctk.CTkButton(
            line, text="Cancel", width=90, height=24,
            fg_color="transparent", border_width=1,
            text_color=TEXT_SECONDARY,
            command=self._build,
        ).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------ chrome #

    def _flash(self, text, error=False):
        """One-line feedback under the page title."""

        if getattr(self, "_status", None) is not None:
            self._status.destroy()
        self._status = ctk.CTkLabel(
            self,
            text=text,
            font=SMALL_FONT,
            text_color=ERROR if error else SUCCESS,
        )
        self._status.pack(pady=(6, 0))
