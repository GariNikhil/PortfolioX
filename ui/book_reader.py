"""Read a book from the shelf inside the app.

The Book Library's notes are a summary; this window shows the book
itself. Text comes from :mod:`books.library`, which extracts it locally
and caches it, so the reader never touches the network.

A long PDF takes a while to parse page by page, so extraction runs on a
background thread and pages appear in the window as they are ready. The
first open of a book shows a progress bar; after that the cache makes it
instant.

One window per book: opening the same book again brings the existing
window forward instead of stacking a second copy.
"""

from __future__ import annotations

import collections
import queue
import threading
import tkinter as tk

import customtkinter as ctk

from books import library
from ui.theme import *

FONT_SIZES = (12, 14, 16, 18, 20, 22, 26)
FONT_DEFAULT = 1
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 800

# Small window that remembers its size for the rest of the session.
_settings = {"font": FONT_DEFAULT}


class BookReader(ctk.CTkToplevel):
    """A window that renders one book as pages of selectable text."""

    def __init__(self, master, book):
        super().__init__(master, fg_color=BACKGROUND)

        self.book = book
        self.source = None
        self.cached = False
        self.unit = "page"

        self._queue = queue.Queue()
        self._pending = collections.deque()
        self._stop = threading.Event()
        self._running = False
        self._pumping = False
        self._offsets = []
        self._total = 0
        self._placed = 0
        self._find_position = "1.0"

        self.title(f"{book.short_title} · {book.author}")
        self.configure(fg_color=BACKGROUND)
        self.minsize(600, 460)
        self._place_window()

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", self._escape)
        self.bind("<Control-f>", self._open_find)
        self.bind("<Control-Left>", lambda _event: self.go_page(-1))
        self.bind("<Control-Right>", lambda _event: self.go_page(1))

        self.after(80, self._begin)

    # ---------------- Layout ---------------- #

    def _place_window(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(DEFAULT_WIDTH, screen_width - 120)
        height = min(DEFAULT_HEIGHT, screen_height - 140)
        left = (screen_width - width) // 2
        top = max(30, (screen_height - height) // 3)
        self.geometry(f"{width}x{height}+{left}+{top}")

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=PADDING, pady=(14, 6))

        ctk.CTkLabel(
            header,
            text=self.book.short_title,
            font=HEADING_FONT,
            text_color=TEXT,
            anchor="w",
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Close",
            width=90,
            height=32,
            font=SMALL_FONT,
            fg_color=CARD,
            hover_color=BORDER,
            text_color=TEXT,
            command=self.close,
        ).pack(side="right")

        self.source_label = ctk.CTkLabel(
            header,
            text=f"{self.book.author} · {self.book.year}",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        )
        self.source_label.pack(side="left", padx=12)

        # ---------------- Toolbar ---------------- #

        toolbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        toolbar.pack(fill="x", padx=PADDING, pady=(0, 8))

        def tool_button(text, command, width=70, **extra):
            button = ctk.CTkButton(
                toolbar,
                text=text,
                width=width,
                height=30,
                font=SMALL_FONT,
                fg_color="transparent",
                hover_color=BORDER,
                text_color=TEXT,
                command=command,
                **extra,
            )
            button.pack(side="left", padx=(8, 0), pady=8)
            return button

        tool_button("A−", lambda: self.change_font(-1), width=46)
        tool_button("A+", lambda: self.change_font(1), width=46)
        tool_button("Find", self._open_find, width=64)

        separator = ctk.CTkFrame(toolbar, fg_color=BORDER, width=1, height=22)
        separator.pack(side="left", padx=12, pady=10)

        tool_button("◀", lambda: self.go_page(-1), width=42)
        tool_button("▶", lambda: self.go_page(1), width=42)

        self.page_entry = ctk.CTkEntry(
            toolbar,
            width=76,
            height=30,
            font=SMALL_FONT,
            justify="center",
        )
        self.page_entry.pack(side="left", padx=(8, 4), pady=8)
        self.page_entry.bind("<Return>", self._jump_from_entry)

        self.page_label = ctk.CTkLabel(
            toolbar,
            text="opening…",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        )
        self.page_label.pack(side="left", padx=(0, 8))

        self.percent_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=SMALL_FONT,
            text_color=ACCENT,
        )
        self.percent_label.pack(side="right", padx=(0, 12))

        # ---------------- Find bar ---------------- #

        self.find_bar = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=8)
        self.find_var = tk.StringVar()
        self.find_entry = ctk.CTkEntry(
            self.find_bar,
            textvariable=self.find_var,
            width=320,
            height=30,
            font=SMALL_FONT,
            placeholder_text="Find in this book…",
        )
        self.find_entry.pack(side="left", padx=8, pady=8)
        self.find_entry.bind("<Return>", lambda _event: self.find_next())
        self.find_entry.bind("<Shift-Return>",
                             lambda _event: self.find_next(backwards=True))

        ctk.CTkButton(
            self.find_bar,
            text="Next",
            width=64,
            height=30,
            font=SMALL_FONT,
            fg_color=ACCENT,
            hover_color=SUCCESS,
            text_color=SIDEBAR,
            command=lambda: self.find_next(),
        ).pack(side="left", padx=(0, 6), pady=8)

        ctk.CTkButton(
            self.find_bar,
            text="Close",
            width=64,
            height=30,
            font=SMALL_FONT,
            fg_color="transparent",
            hover_color=BORDER,
            text_color=TEXT,
            command=self._close_find,
        ).pack(side="left", pady=8)

        self.find_status = ctk.CTkLabel(
            self.find_bar,
            text="",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
        )
        self.find_status.pack(side="left", padx=10)

        # ---------------- Text ---------------- #

        holder = ctk.CTkFrame(self, fg_color=BACKGROUND)
        holder.pack(fill="both", expand=True, padx=PADDING, pady=(0, 8))

        size = FONT_SIZES[_settings["font"]]
        self.text = tk.Text(
            holder,
            wrap="word",
            bg=BACKGROUND,
            fg=TEXT,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=44,
            pady=18,
            spacing2=3,
            spacing3=12,
            font=(FONT_FAMILY, size),
            selectbackground=CARD,
            selectforeground=TEXT,
            insertwidth=0,
            cursor="arrow",
        )
        self.text.pack(side="left", fill="both", expand=True)

        scrollbar = ctk.CTkScrollbar(holder, command=self.text.yview, width=14)
        scrollbar.pack(side="right", fill="y", padx=(6, 0))
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.tag_configure("page_label", foreground=BORDER,
                                font=(FONT_FAMILY, max(10, size - 4)),
                                justify="center", spacing1=6, spacing3=10)
        self.text.tag_configure("find", background=WARNING, foreground=SIDEBAR)
        self.text.configure(state="disabled")

        for sequence in ("<ButtonRelease-1>", "<MouseWheel>", "<KeyRelease>"):
            self.text.bind(sequence, self._sync_page_label, add="+")

        # ---------------- Footer ---------------- #

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=PADDING, pady=(0, 12))

        self.progress = ctk.CTkProgressBar(footer, width=200, height=8,
                                           progress_color=ACCENT)
        self.progress.set(0)
        self.progress.pack(side="left")

        self.status = ctk.CTkLabel(
            footer,
            text="Looking for the book file…",
            font=SMALL_FONT,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.status.pack(side="left", padx=12)

    # ---------------- Loading ---------------- #

    def _begin(self):
        if not self.winfo_exists():
            return

        self.source = library.source_for(self.book)
        if self.source is None:
            self._show_missing()
            return

        self.unit = "section" if self.source.kind == "markdown" else "page"
        cached = library.read_cache(self.book, self.source)
        if cached is not None:
            self.cached = True
            self._total = cached.page_count
            self.source_label.configure(
                text=f"{self.book.author} · {self.source.label} · cached"
            )
            self.progress.set(1)
            self.status.configure(text="Loaded from the local cache.")
            self._enqueue(cached.pages)
            return

        self.source_label.configure(
            text=f"{self.book.author} · {self.source.label}"
        )
        self.status.configure(
            text=f"Preparing the first {self.unit}s from the file…"
        )
        self._running = True
        thread = threading.Thread(target=self._extract, daemon=True)
        thread.start()
        self.after(80, self._poll)

    def _extract(self):
        """Background: parse the book and hand pages over as they arrive."""

        source = self.source
        pages = []
        try:
            self._queue.put(("total", library.page_count(source)))
            for chunk in library.extract_chunks(source):
                if self._stop.is_set():
                    return
                pages.extend(chunk)
                self._queue.put(("pages", list(chunk)))
            if not self._stop.is_set():
                library.write_cache(self.book, source, pages)
                self._queue.put(("done", len(pages)))
        except Exception as error:  # a bad file should explain itself
            self._queue.put(("error", str(error)))

    def _poll(self):
        """Main thread: move anything the worker produced into the window."""

        if not self.winfo_exists():
            return

        finished = False
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "total":
                    self._total = payload
                elif kind == "pages":
                    self._enqueue(payload)
                elif kind == "done":
                    self._total = payload
                    self.progress.set(1)
                    self.percent_label.configure(text="")
                    self.status.configure(
                        text=f"{payload} {self.unit}s · {self.source.label} · cached"
                    )
                    finished = True
                elif kind == "error":
                    self.status.configure(text=f"Could not read the file: {payload}")
                    self.progress.set(0)
                    finished = True
        except queue.Empty:
            pass

        if finished:
            self._running = False
            return
        self.after(80, self._poll)

    def _enqueue(self, pages):
        self._pending.extend(pages)
        if not self._pumping:
            self._pumping = True
            self.after(1, self._pump)

    def _pump(self):
        """Insert a few pages per idle slice, keeping the window responsive."""

        if not self.winfo_exists():
            return

        for _ in range(6):
            if not self._pending:
                break
            self._append_page(self._pending.popleft())

        if self._pending:
            self.after(1, self._pump)
            return

        self._pumping = False
        if self._running and self._total:
            fraction = min(1.0, self._placed / self._total)
            self.progress.set(fraction)
            self.percent_label.configure(text=f"{fraction:.0%}")
            self.status.configure(
                text=f"Reading the file · {self._placed} of {self._total} "
                     f"{self.unit}s ready"
            )
        self._sync_page_label()

    def _append_page(self, body):
        self._placed += 1
        number = self._placed

        top = self.text.yview()[0]
        self.text.configure(state="normal")

        if number > 1:
            self.text.insert("end", "\n")

        self.text.insert("end", f"{self.unit} {number}\n", ("page_label",))
        start = self.text.index("end-1c")
        self.text.insert("end", (body or "").strip() + "\n", ("body",))
        self.text.configure(state="disabled")

        self._offsets.append(start)
        if top > 0 and number > 8:
            self.text.yview_moveto(top)

    def _show_missing(self):
        self.progress.set(0)
        self.percent_label.configure(text="")
        self.status.configure(text="The book file is not on this computer.")

        message = (
            f"{self.book.title}\n{self.book.author}\n\n"
            "The reader looks for this file in the shelf folder:\n\n"
            f"    {library.BOOKS_FOLDER / self.book.file_name}\n\n"
            "That folder is personal material: it is not part of the source "
            "code and the app never downloads books. To read it here, copy "
            "the file into the folder above and open the book again.\n\n"
            "The notes on the book card are still available in the Library."
        )

        self.text.configure(state="normal")
        self.text.insert("end", message, ("body",))
        self.text.configure(state="disabled")
        self.page_label.configure(text="not available")

    # ---------------- Navigation ---------------- #

    @staticmethod
    def _index_value(index):
        line, _, column = index.partition(".")
        return int(line) + int(column or 0) / 1000

    def current_page(self):
        """The page whose text is at the top of the window."""

        if not self._offsets:
            return 0
        position = self._index_value(self.text.index("@0,0"))
        number = 1
        for index, offset in enumerate(self._offsets, start=1):
            if self._index_value(offset) <= position + 0.5:
                number = index
        return number

    def _sync_page_label(self, _event=None):
        shown = self.current_page()
        total = max(self._total, self._placed)
        if not total:
            self.page_label.configure(text="opening…")
            return
        self.page_label.configure(text=f"{self.unit} {shown} of {total}")
        if self.focus_get() is not self.page_entry:
            self.page_entry.delete(0, "end")
            self.page_entry.insert(0, str(shown))

    def go_page(self, step):
        """Jump one page forward or back."""

        if not self._offsets:
            return
        target = self.current_page() + step
        target = max(1, min(len(self._offsets), target))
        self.jump_to(target)

    def jump_to(self, number):
        if not self._offsets:
            return
        number = max(1, min(len(self._offsets), int(number)))
        self.text.yview(self._offsets[number - 1])
        self._sync_page_label()

    def _jump_from_entry(self, _event=None):
        raw = self.page_entry.get().strip()
        digits = "".join(character for character in raw if character.isdigit())
        if digits:
            self.jump_to(int(digits))
        else:
            self._sync_page_label()

    # ---------------- Font and find ---------------- #

    def change_font(self, step):
        index = max(0, min(len(FONT_SIZES) - 1, _settings["font"] + step))
        _settings["font"] = index
        size = FONT_SIZES[index]
        self.text.configure(font=(FONT_FAMILY, size))
        self.text.tag_configure("page_label",
                                font=(FONT_FAMILY, max(10, size - 4)))

    def _open_find(self, _event=None):
        self.find_bar.pack(fill="x", padx=PADDING, pady=(0, 8),
                           before=self.text.master)
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")

    def _close_find(self):
        self.find_bar.pack_forget()
        self.text.tag_remove("find", "1.0", "end")

    def find_next(self, backwards=False):
        needle = self.find_var.get().strip()
        if not needle:
            self.find_status.configure(text="Type a word to find.")
            return

        self.text.tag_remove("find", "1.0", "end")
        start = self._find_position
        stop = "1.0" if backwards else "end"
        found = self.text.search(needle, start, stopindex=stop,
                                 nocase=True, backwards=backwards)
        if not found:  # wrap around the ends of the book
            found = self.text.search(needle, stop, stopindex=start,
                                     nocase=True, backwards=backwards)
        if not found:
            self.find_status.configure(text="No match.")
            self._find_position = "1.0"
            return

        end = f"{found}+{len(needle)}c"
        self.text.tag_add("find", found, end)
        self.text.tag_raise("find")
        self.text.see(found)
        self.text.yview_moveto(max(0.0, self.text.yview()[0] - 0.08))
        self._find_position = end
        self.find_status.configure(text="Match found.")

    # ---------------- Closing ---------------- #

    def _escape(self, _event=None):
        if self.find_bar.winfo_ismapped():
            self._close_find()
        else:
            self.close()

    def close(self):
        self._stop.set()
        self._running = False
        OPEN_READERS.pop(self.book.key, None)
        self.destroy()


OPEN_READERS = {}


def open_reader(master, book):
    """Open ``book`` in a reader window, or bring its window forward."""

    existing = OPEN_READERS.get(book.key)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_force()
        return existing

    reader = BookReader(master, book)
    OPEN_READERS[book.key] = reader
    reader.lift()
    reader.focus_force()
    return reader
