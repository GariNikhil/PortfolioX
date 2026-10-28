"""Settings page: vault health, stored-password entries, database location."""

import customtkinter as ctk

from database import db
from security import vault
from ui.theme import *


class SettingsPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="Settings",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 16))

        self._vault_section()
        self._database_section()

    def _vault_section(self):
        """Password-vault health, from security.vault.status()."""

        ctk.CTkLabel(
            self,
            text="🔐 Password vault",
            font=HEADING_FONT,
            text_color=TEXT,
        ).pack(anchor="w", padx=PADDING)

        try:
            report = vault.status()
            entries = vault.list_entries()
        except VaultError as error:
            ctk.CTkLabel(
                self,
                text=f"Vault problem: {error}",
                font=BODY_FONT,
                text_color=ERROR,
            ).pack(anchor="w", padx=PADDING, pady=6)
            return

        key_state = "configured" if report["key_configured"] else "not configured"
        lines = (
            f"Keyring backend: {report['backend']}",
            f"Encryption key: {key_state}",
            f"Stored passwords: {report['entries']}",
            f"Vault file: {report['vault_file']}",
        )
        for line in lines:
            ctk.CTkLabel(
                self,
                text=line,
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
                anchor="w",
            ).pack(anchor="w", padx=PADDING, pady=1)

        if entries:
            ctk.CTkLabel(
                self,
                text="Stored entries (no secrets shown):",
                font=SMALL_FONT,
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=PADDING, pady=(10, 2))
            for entry in entries:
                pattern = entry["file_pattern"] or "(all files of this kind)"
                ctk.CTkLabel(
                    self,
                    text=f"  • {entry['kind']}  -  {pattern}  -  {entry['updated_at']}",
                    font=SMALL_FONT,
                    text_color=TEXT,
                    anchor="w",
                ).pack(anchor="w", padx=PADDING)

    def _database_section(self):
        """Where the data lives (read-only information)."""

        ctk.CTkLabel(
            self,
            text="🗄 Database",
            font=HEADING_FONT,
            text_color=TEXT,
        ).pack(anchor="w", padx=PADDING, pady=(24, 4))

        ctk.CTkLabel(
            self,
            text=f"Portfolio database: {db.DB_PATH}",
            font=BODY_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(anchor="w", padx=PADDING)

        ctk.CTkLabel(
            self,
            text="Backups and exports arrive in later phases.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(anchor="w", padx=PADDING, pady=1)
