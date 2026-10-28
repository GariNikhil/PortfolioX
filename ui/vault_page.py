"""Pass Vault page: manage stored passwords (never displays secrets).

Entries are listed from security.vault (kind + file pattern + updated
time only); adding stores a new password encrypted locally, deleting
removes it. Passwords are typed into a masked field and never shown.
"""

import customtkinter as ctk

from security import vault
from security.vault import VaultError
from ui.theme import *


class VaultPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="🔑 Pass Vault",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Passwords for encrypted files (contract notes), stored "
                 "encrypted on this machine only.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._add_form()
        self._entries_section()

    # ---------------- Add form ---------------- #

    def _add_form(self):
        form = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        form.pack(fill="x", padx=PADDING, pady=(0, PADDING))

        ctk.CTkLabel(
            form, text="Add a password",
            font=HEADING_FONT, text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 8))

        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkLabel(row, text="Kind (e.g. CONTRACT_NOTE_PDF)",
                     font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._kind_entry = ctk.CTkEntry(row, width=260)
        self._kind_entry.grid(row=0, column=1, padx=(0, 20))

        ctk.CTkLabel(row, text="File pattern (optional, e.g. *contract*.pdf)",
                     font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).grid(row=0, column=2, sticky="w", padx=(0, 8))
        self._pattern_entry = ctk.CTkEntry(row, width=260)
        self._pattern_entry.grid(row=0, column=3, padx=(0, 20))

        ctk.CTkLabel(row, text="Password",
                     font=SMALL_FONT, text_color=TEXT_SECONDARY
                     ).grid(row=0, column=4, sticky="w", padx=(0, 8))
        self._password_entry = ctk.CTkEntry(row, width=220, show="*")
        self._password_entry.grid(row=0, column=5, padx=(0, 20))

        ctk.CTkButton(row, text="Store", width=100,
                      command=self._store).grid(row=0, column=6)

        ctk.CTkLabel(
            form,
            text="Leave the file pattern empty for a kind-wide password; "
                 "a per-file pattern overrides it.",
            font=SMALL_FONT, text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _store(self):
        kind = self._kind_entry.get().strip()
        pattern = self._pattern_entry.get().strip() or None
        password = self._password_entry.get()

        try:
            vault.store_password(kind, password, file_pattern=pattern)
        except VaultError as error:
            self._flash(f"⚠ {error}", ERROR)
            return

        self._password_entry.delete(0, "end")
        self._flash(f"✔ Stored password for {kind}", SUCCESS)
        self._refresh_entries()

    # ---------------- Entries list ---------------- #

    def _entries_section(self):
        self._entries_frame = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=8
        )
        self._entries_frame.pack(fill="both", expand=True,
                                 padx=PADDING, pady=(0, PADDING))
        self._status_label = None
        self._refresh_entries()

    def _refresh_entries(self):
        for child in self._entries_frame.winfo_children():
            child.destroy()

        try:
            entries = vault.list_entries()
        except VaultError as error:
            ctk.CTkLabel(
                self._entries_frame,
                text=f"⚠ Vault unavailable: {error}",
                font=BODY_FONT, text_color=ERROR,
            ).pack(padx=16, pady=16, anchor="w")
            return

        ctk.CTkLabel(
            self._entries_frame,
            text=f"Stored entries ({len(entries)})",
            font=HEADING_FONT, text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(12, 8))

        if not entries:
            ctk.CTkLabel(
                self._entries_frame,
                text="No passwords stored yet.",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=16, pady=(0, 12))
            return

        for entry in entries:
            row = ctk.CTkFrame(self._entries_frame, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)

            pattern = entry["file_pattern"] or "(all files of this kind)"
            ctk.CTkLabel(
                row,
                text=f"{entry['kind']}   ·   {pattern}   ·   "
                     f"updated {entry['updated_at']}",
                font=SMALL_FONT, text_color=TEXT, anchor="w",
            ).pack(side="left", fill="x", expand=True)

            ctk.CTkButton(
                row, text="Delete", width=90, height=26,
                fg_color=ERROR, hover_color="#B71C1C",
                command=lambda e=entry: self._delete(e),
            ).pack(side="right")

    def _delete(self, entry):
        vault.delete_password(entry["kind"],
                              file_pattern=entry["file_pattern"])
        self._flash(f"✔ Deleted entry for {entry['kind']}", SUCCESS)
        self._refresh_entries()

    # ---------------- Feedback ---------------- #

    def _flash(self, message, color):
        if self._status_label is not None:
            self._status_label.destroy()
        self._status_label = ctk.CTkLabel(
            self, text=message, font=SMALL_FONT, text_color=color,
        )
        self._status_label.pack(pady=(0, 8))
