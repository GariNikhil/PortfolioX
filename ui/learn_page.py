"""Learn hub: lessons, book notes, a strategy playbook and a planning path.

All of the content is curated offline from the books in
``referance/books`` and lives in ``ui/learn_content.py`` — nothing here
is fetched from the internet. The hub copies the Holdings tab bar: four
tabs share one content frame, and always opens on Lessons.
"""

import tkinter as tk

import customtkinter as ctk

from ui.learn_content import (
    BOOKS,
    EXTRA_REFERENCES,
    LESSONS,
    PLANNING_PHASES,
    PLAYBOOK,
    REVIEW_CHECKLIST,
    TRACKS,
    TRACK_BY_KEY,
    filter_books,
    source_titles,
)
from ui.theme import *

TAB_NAMES = ("Lessons", "Book Library", "Strategy Playbook", "Planning")

# Starting wrap width; every prose label re-wraps to its card when the
# window (or the calculator panel) changes the available width.
WRAP = 820

CARD_TITLE_FONT = (FONT_FAMILY, 19, "bold")
SECTION_FONT = (FONT_FAMILY, 13, "bold")

LEVEL_COLORS = {
    "Beginner": ACCENT,
    "Intermediate": WARNING,
    "Advanced": ERROR,
}


# ---------------- Shared building blocks ---------------- #


def _wrap_to_container(label, container, side_pad=16):
    """Keep ``label`` wrapped to the width of its card.

    CTk widths are logical while ``winfo_width`` is physical, so the
    event width is divided by the DPI scale before it becomes a
    wraplength. The 16 px threshold stops a height change from
    re-triggering a wrap that would only differ by a pixel.
    """

    state = {"wrap": WRAP}

    def on_configure(event):
        try:
            scale = ctk.ScalingTracker.get_window_dpi_scaling(label) or 1.0
        except Exception:  # not on Windows / not mapped yet
            scale = 1.0
        width = max(240, int(event.width / scale) - 2 * side_pad - 8)
        if abs(width - state["wrap"]) >= 16:
            state["wrap"] = width
            label.configure(wraplength=width)

    container.bind("<Configure>", on_configure, add="+")
    return label


def _prose(parent, text, font=BODY_FONT, color=TEXT_SECONDARY, side_pad=16,
           pady=(0, 3)):
    """A wrapping paragraph label that tracks its card's width."""

    label = ctk.CTkLabel(
        parent,
        text=text,
        font=font,
        text_color=color,
        wraplength=WRAP,
        justify="left",
        anchor="w",
    )
    label.pack(fill="x", padx=side_pad, pady=pady)
    return _wrap_to_container(label, parent, side_pad)


def _bullets(parent, heading, items, numbered=False):
    """A section heading followed by bullet (or numbered) lines."""

    if not items:
        return

    ctk.CTkLabel(
        parent,
        text=heading,
        font=SECTION_FONT,
        text_color=TEXT,
        anchor="w",
    ).pack(fill="x", padx=16, pady=(10, 2))

    for index, item in enumerate(items, start=1):
        marker = f"{index}." if numbered else "•"
        _prose(parent, f"{marker}  {item}")


def _intro_card(parent, title, text):
    """A soft card that explains what the tab is for."""

    card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=8)
    card.pack(fill="x", pady=(0, 10))

    ctk.CTkLabel(
        card,
        text=title,
        font=HEADING_FONT,
        text_color=TEXT,
        anchor="w",
    ).pack(fill="x", padx=16, pady=(14, 4))

    _prose(card, text, pady=(0, 14))

    return card


def _source_line(parent, keys):
    """The 'From: …' citation under a playbook or planning card."""

    _prose(
        parent,
        f"From: {source_titles(keys)}",
        font=SMALL_FONT,
        color=ACCENT,
        pady=(8, 14),
    )


# ---------------- Lessons ---------------- #


class LessonsTab(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.pack(fill="both", expand=True)

        self.body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        self.body.pack(fill="both", expand=True, padx=PADDING, pady=(8, PADDING))

        _intro_card(
            self.body,
            "Start here",
            f"{len(LESSONS)} short lessons on how the Indian market works, "
            f"plus a library of {len(BOOKS)} books, {len(PLAYBOOK)} "
            f"strategy rules and {len(PLANNING_PHASES)} planning phases. "
            "Read a lesson, then open the Book Library for the notes behind "
            "it. Everything is offline and stored on this computer.",
        )

        for heading, text in LESSONS:
            card = ctk.CTkFrame(self.body, fg_color=CARD, corner_radius=8)
            card.pack(fill="x", pady=6)

            ctk.CTkLabel(
                card,
                text=heading,
                font=CARD_TITLE_FONT,
                text_color=TEXT,
                anchor="w",
            ).pack(fill="x", padx=16, pady=(12, 4))

            _prose(card, text, pady=(0, 14))


# ---------------- Book Library ---------------- #


class BookCard(ctk.CTkFrame):
    """One book: title, thesis, and notes that expand on request."""

    def __init__(self, parent, book):
        super().__init__(parent, fg_color=CARD, corner_radius=8)
        self.pack(fill="x", pady=6)

        self.book = book
        self.expanded = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 0))

        ctk.CTkLabel(
            header,
            text=book.level,
            font=SMALL_FONT,
            text_color=LEVEL_COLORS.get(book.level, TEXT_SECONDARY),
        ).pack(side="right", padx=(12, 0))

        title = ctk.CTkLabel(
            header,
            text=book.title,
            font=CARD_TITLE_FONT,
            text_color=TEXT,
            anchor="w",
            justify="left",
            wraplength=WRAP - 120,
        )
        title.pack(side="left", fill="x", expand=True)
        _wrap_to_container(title, header, side_pad=60)

        track = TRACK_BY_KEY[book.track]
        ctk.CTkLabel(
            self,
            text=f"{book.author} · {book.year} · {track.title}",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(2, 6))

        _prose(self, book.thesis, color=TEXT, pady=(0, 0))

        self.toggle = ctk.CTkButton(
            self,
            text="Notes ▾",
            width=110,
            height=30,
            font=SMALL_FONT,
            fg_color="transparent",
            hover_color=BORDER,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            command=self.toggle_notes,
        )
        self.toggle.pack(anchor="w", padx=16, pady=(8, 12))

        self.details = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=6)
        _bullets(self.details, "Key ideas", book.ideas)
        _bullets(self.details, "Tricks & rules", book.tricks)
        _bullets(self.details, "Use it in PortfolioX", book.planning)

        _prose(
            self.details,
            f"Source file: referance/books/{book.file_name}",
            font=SMALL_FONT,
            pady=(10, 12),
        )

    def toggle_notes(self):
        if self.expanded:
            self.details.pack_forget()
            self.toggle.configure(text="Notes ▾")
        else:
            self.details.pack(fill="x", padx=16, pady=(0, 14))
            self.toggle.configure(text="Notes ▴")
        self.expanded = not self.expanded


class BookLibraryTab(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.pack(fill="both", expand=True)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=PADDING, pady=(8, 4))

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            controls,
            textvariable=self.search_var,
            width=340,
            height=36,
            font=SMALL_FONT,
            placeholder_text="Search titles, ideas, rules…",
        )
        self.search_entry.pack(side="left")
        self.search_var.trace_add("write", lambda *_args: self.refresh())

        self.track_var = tk.StringVar(value="All tracks")
        self.track_menu = ctk.CTkOptionMenu(
            controls,
            values=["All tracks"] + [track.title for track in TRACKS],
            variable=self.track_var,
            width=230,
            height=36,
            font=SMALL_FONT,
            command=lambda _choice: self.refresh(),
        )
        self.track_menu.pack(side="left", padx=8)

        self.count_label = ctk.CTkLabel(
            controls,
            text="",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        )
        self.count_label.pack(side="right")

        self.body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        self.body.pack(fill="both", expand=True, padx=PADDING, pady=(0, PADDING))

        self.cards = []
        self.refresh()

    def selected_track(self):
        """The track key for the menu choice, or None for every track."""

        title = self.track_var.get()
        for track in TRACKS:
            if track.title == title:
                return track.key
        return None

    def refresh(self):
        for card in self.cards:
            card.destroy()
        self.cards = []

        books = filter_books(self.search_var.get(), self.selected_track())
        self.count_label.configure(
            text=f"{len(books)} of {len(BOOKS)} books"
        )

        if not books:
            empty = ctk.CTkLabel(
                self.body,
                text="No book matches that search. Try another word or "
                     "switch the track back to All tracks.",
                font=BODY_FONT,
                text_color=TEXT_SECONDARY,
                anchor="w",
            )
            empty.pack(fill="x", padx=16, pady=20)
            self.cards.append(empty)
            return

        for book in books:
            self.cards.append(BookCard(self.body, book))


# ---------------- Strategy Playbook ---------------- #


class PlaybookTab(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.pack(fill="both", expand=True)

        self.body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        self.body.pack(fill="both", expand=True, padx=PADDING, pady=(8, PADDING))

        _intro_card(
            self.body,
            "Strategy playbook",
            f"{len(PLAYBOOK)} rules distilled from the {len(BOOKS)} books "
            "on the shelf. Each rule cites the books it came from, so you "
            "can read the source before changing the rule. Rules are "
            "checklists, not predictions.",
        )

        for number, entry in enumerate(PLAYBOOK, start=1):
            card = ctk.CTkFrame(self.body, fg_color=CARD, corner_radius=8)
            card.pack(fill="x", pady=6)

            ctk.CTkLabel(
                card,
                text=f"{number}. {entry.title}",
                font=CARD_TITLE_FONT,
                text_color=TEXT,
                anchor="w",
                justify="left",
                wraplength=WRAP,
            ).pack(fill="x", padx=16, pady=(12, 2))

            _prose(card, entry.principle, pady=(0, 4))

            _bullets(card, "Rules", entry.rules, numbered=True)
            _source_line(card, entry.sources)


# ---------------- Planning ---------------- #


class PlanningTab(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.pack(fill="both", expand=True)

        self.body = ctk.CTkScrollableFrame(self, fg_color=BACKGROUND)
        self.body.pack(fill="both", expand=True, padx=PADDING, pady=(8, PADDING))

        _intro_card(
            self.body,
            "Planning path",
            f"{len(PLANNING_PHASES)} phases from saving to reviewing. Work "
            "top to bottom the first time; after that the review phase sets "
            "the calendar. Every phase lists the books it draws on.",
        )

        for number, phase in enumerate(PLANNING_PHASES, start=1):
            card = ctk.CTkFrame(self.body, fg_color=CARD, corner_radius=8)
            card.pack(fill="x", pady=6)

            ctk.CTkLabel(
                card,
                text=f"Phase {number} · {phase.title}",
                font=CARD_TITLE_FONT,
                text_color=TEXT,
                anchor="w",
                justify="left",
                wraplength=WRAP,
            ).pack(fill="x", padx=16, pady=(12, 2))

            _prose(card, phase.summary, pady=(0, 4))

            _bullets(card, "Do this", phase.actions, numbered=True)
            _source_line(card, phase.sources)

        checklist = ctk.CTkFrame(self.body, fg_color=CARD, corner_radius=8)
        checklist.pack(fill="x", pady=(10, 6))

        ctk.CTkLabel(
            checklist,
            text="Review checklist",
            font=CARD_TITLE_FONT,
            text_color=TEXT,
            anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 2))

        _prose(
            checklist,
            "Run through this at the calendar review. Any unchecked line "
            "is next week's job.",
            font=SMALL_FONT,
            pady=(0, 4),
        )

        _bullets(checklist, "Checks", REVIEW_CHECKLIST)

        _bullets(
            checklist,
            "Also on the shelf",
            [f"{name} — {description}" for name, description in EXTRA_REFERENCES],
        )

        ctk.CTkFrame(checklist, fg_color="transparent", height=8).pack()


# ---------------- Hub ---------------- #


TABS = {
    "Lessons": LessonsTab,
    "Book Library": BookLibraryTab,
    "Strategy Playbook": PlaybookTab,
    "Planning": PlanningTab,
}


class LearnPage(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color=BACKGROUND)
        self.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self,
            text="📚 Learn",
            font=TITLE_FONT,
            text_color=TEXT,
        ).pack(pady=(24, 2))

        ctk.CTkLabel(
            self,
            text="Lessons, book notes, a strategy playbook and a planning "
                 "path — all offline.",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 10))

        # ---------------- Tab bar ---------------- #

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=PADDING, pady=(0, 4))

        self.tab_buttons = {}
        for name in TAB_NAMES:
            btn = ctk.CTkButton(
                bar,
                text=name,
                width=150,
                height=36,
                font=SMALL_FONT,
                corner_radius=18,
                fg_color="transparent",
                text_color=TEXT,
                hover_color=BORDER,
                command=lambda x=name: self.show_tab(x),
            )
            btn.pack(side="left", padx=4)
            self.tab_buttons[name] = btn

        # ---------------- Content ---------------- #

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)

        self.current_tab = None
        self.current_page = None
        self.show_tab(TAB_NAMES[0])  # always opens on Lessons

    def show_tab(self, name):
        factory = TABS.get(name)
        if factory is None:
            return
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page = factory(self.content)
        self.current_tab = name

        for tab_name, btn in self.tab_buttons.items():
            btn.configure(
                fg_color=ACCENT if tab_name == name else "transparent",
                text_color=SIDEBAR if tab_name == name else TEXT,
                hover_color=ACCENT if tab_name == name else BORDER,
            )
