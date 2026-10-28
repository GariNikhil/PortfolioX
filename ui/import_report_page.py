"""Contract Note report page: audit of contract-note import attempts.

Lists the imports table filtered to CONTRACT_NOTE_PDF — file, date,
status — so skipped or failed notes are visible without opening the DB.
"""

import customtkinter as ctk

from database.manager import get_imports
from ui.theme import *


class ImportReportPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="📄 Contract Note Report",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(40, 4))

        ctk.CTkLabel(
            self,
            text="Every contract-note PDF import attempt and its outcome.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 16))

        self._table()

    def _table(self):
        imports = get_imports("CONTRACT_NOTE_PDF")

        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

        if not imports:
            ctk.CTkLabel(
                frame,
                text="No contract-note imports recorded yet.",
                font=BODY_FONT, text_color=TEXT_SECONDARY,
            ).pack(padx=16, pady=16, anchor="w")
            return

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        for text, width, anchor in (
            ("File", 460, "w"), ("Imported", 180, "w"), ("Status", 140, "w"),
        ):
            ctk.CTkLabel(header, text=text, width=width, anchor=anchor,
                         font=SMALL_FONT, text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=2)

        ok = sum(1 for row in imports if str(row["status"]).upper() == "OK")
        ctk.CTkLabel(
            frame,
            text=f"{len(imports)} imports · {ok} OK · "
                 f"{len(imports) - ok} skipped/failed",
            font=HEADING_FONT, text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        for row in imports:
            line = ctk.CTkFrame(frame, fg_color="transparent")
            line.pack(fill="x", padx=16, pady=2)
            status = str(row["status"]).upper()
            color = SUCCESS if status == "OK" else WARNING
            ctk.CTkLabel(line, text=row["filename"], width=460, anchor="w",
                         font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=str(row["imported_date"]), width=180,
                         anchor="w", font=BODY_FONT, text_color=TEXT
                         ).pack(side="left", padx=2)
            ctk.CTkLabel(line, text=status, width=140, anchor="w",
                         font=BODY_FONT, text_color=color
                         ).pack(side="left", padx=2)
