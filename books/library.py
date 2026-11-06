"""The book shelf: turn a book file into pages of plain text.

``referance/books`` is personal, gitignored material and is never shipped
with the app. This module resolves a :class:`ui.learn_content.Book` to the
file on disk, extracts its text locally (``pypdf`` for PDFs, a plain read
for the Markdown conversions), and caches the result under
``data/book_text`` so a book only has to be parsed once. Nothing is
downloaded and no network call is made.

The module imports no Tk code, so the parsing rules are unit-tested
headless in ``books/test_library.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from paths import books_dir, data_dir

# The shelf is personal material beside the app, and the extract cache
# sits beside the database, so both survive a frozen build (see paths).
BOOKS_FOLDER = books_dir()
CACHE_FOLDER = data_dir() / "book_text"

# Pages are stored back to back in one cache file, separated by a form
# feed: it does not occur in extracted prose and survives a round trip.
PAGE_BREAK = "\f"

# PDF text extraction costs a fraction of a second per page, so a long
# book is parsed in batches and handed to the reader as it is ready.
CHUNK_PAGES = 10

# Markdown conversions have no pages; they are cut into evenly sized
# reading pages so page navigation still works.
MARKDOWN_PAGE_CHARS = 3200

DEFAULT_PAGE_CHARS = 3200

_TRANSLATE = str.maketrans({
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\u00ad": "",
    "\u200b": "",
    "\u00a0": " ",
    "\u2007": " ",
    "\u202f": " ",
    "\t": " ",
})

_SPACES = re.compile(r"[ ]{2,}")
_PAGE_NUMBER = re.compile(
    r"^(?:page\s+)?[\-–—]?\s*\d{1,4}\s*[\-–—]?$"
    r"|^page\s+\d+\s+(?:of|/)\s+\d+$",
    re.IGNORECASE,
)
# Lower-case only, and an explicit list: "mix", "mild" and "civil" are
# words, not front-matter page numbers.
_ROMAN_PAGES = frozenset(
    "i ii iii iv v vi vii viii ix x xi xii xiii xiv xv xvi xvii xviii xix xx "
    "xxi xxii xxiii xxiv xxv xxvi xxvii xxviii xxix xxx".split()
)
_BULLET = re.compile(r"^(?:[•▪◦·*–—-]|\(?\d{1,2}[.)])\s+")
_TERMINAL = (".", "!", "?", ":", ";", "”", '"', "’", "'")
_OPENERS = "\"'“‘([—–"


@dataclass(frozen=True)
class Source:
    """The file a book is read from."""

    path: Path
    kind: str  # "markdown" or "pdf"
    modified: float
    size: int

    @property
    def label(self):
        return "Markdown" if self.kind == "markdown" else "PDF"


@dataclass(frozen=True)
class BookText:
    """Cleaned pages plus enough metadata to show them."""

    pages: tuple[str, ...]
    kind: str
    source_name: str
    from_cache: bool = False

    @property
    def page_count(self):
        return len(self.pages)

    @property
    def characters(self):
        return sum(len(page) for page in self.pages)


# ---------------- Resolving the file ---------------- #


def _source(path, kind):
    stat = path.stat()
    return Source(path, kind, stat.st_mtime, stat.st_size)


def source_for(book, folder=BOOKS_FOLDER):
    """Return the best file for ``book``: a Markdown conversion or the PDF.

    The Markdown conversions sit beside the PDFs with the same stem and
    are already reflowed, so they read better and parse instantly. When
    there is no conversion the PDF is used. ``None`` means the book is
    not on this computer.
    """

    folder = Path(folder)
    pdf = folder / book.file_name
    markdown = pdf.with_suffix(".md")

    if markdown.is_file():
        return _source(markdown, "markdown")
    if pdf.is_file():
        return _source(pdf, "pdf")
    return None


# ---------------- Cleaning PDF pages ---------------- #


def _prepare(page):
    """Normalise one raw page into a list of stripped lines."""

    if not isinstance(page, str):  # a page may arrive as prepared lines
        page = "\n".join(page)
    text = page.replace("\r\n", "\n").replace("\r", "\n").translate(_TRANSLATE)
    text = _SPACES.sub(" ", text)
    return [line.strip() for line in text.split("\n")]


def _head_key(line):
    """A page-furniture key: case, punctuation and page numbers drop out.

    "352 Chapter 14" and "Chapter 14 360" share the key "chapter", so a
    header that swaps sides between even and odd pages is still spotted.
    Long lines and finished sentences are never treated as furniture, so
    body text cannot be mistaken for a header.
    """

    if len(line) > 60 or line.endswith(_TERMINAL):
        return ""
    return re.sub(r"[^A-Za-z]+", " ", line).strip().lower()


def running_heads(pages, share=0.35, minimum=3):
    """Lines that repeat at the top or bottom of a batch of pages.

    A title printed at the top of every page — or the page number under
    the block — otherwise lands in the middle of every paragraph. Only
    the first and last two lines of a page are considered, so a sentence
    that happens to repeat in the body is never mistaken for furniture.
    Digits are masked so "... 355" on one page and "... 356" on the next
    still match.
    """

    if len(pages) < 4:
        return set()

    counts = {}
    for lines in pages:
        edges = [line for line in lines[:2] + lines[-2:] if line]
        for key in {_head_key(line) for line in edges}:
            if key:
                counts[key] = counts.get(key, 0) + 1

    threshold = max(minimum, int(round(len(pages) * share)))
    return {key for key, count in counts.items() if count >= threshold}


def _is_furniture(line, heads):
    stripped = line.strip()
    if not stripped:
        return True
    if not any(character.isalnum() for character in stripped):
        return True
    if _PAGE_NUMBER.match(stripped) or stripped.lower() in _ROMAN_PAGES:
        return True
    return _head_key(stripped) in heads


def _ends_sentence(line):
    return line.endswith(_TERMINAL)


def _starts_sentence(line):
    return bool(line) and (line[:1].isupper() or line[:1] in _OPENERS
                           or line[:1].isdigit())


def reflow(lines):
    """Join hard-wrapped lines back into paragraphs.

    PDF text arrives one visual line at a time. Lines are joined with a
    space, a line broken on a hyphen is sewn back together, and a
    paragraph ends where a line finishes a sentence and the next line
    starts one — or where a line is much shorter than the page's usual
    measure. Bullets always start their own paragraph.
    """

    lines = [line.strip() for line in lines if line.strip()]
    if not lines:
        return ""

    lengths = sorted(len(line) for line in lines if len(line) > 40)
    measure = lengths[len(lengths) // 2] if lengths else 0

    paragraphs = []
    current = []

    def flush():
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for line in lines:
        if _BULLET.match(line):
            flush()
            current.append(line)
            continue

        if current:
            previous = current[-1]
            if previous.endswith("-") and len(previous) > 2 and line[:1].islower():
                current[-1] = previous[:-1] + line
                continue
            if previous.endswith("-") and len(previous) > 2 and line[:1].isupper():
                current[-1] = previous + line
                continue
            if _ends_sentence(previous) and _starts_sentence(line):
                flush()
            elif measure and len(previous) < measure * 0.55 and _starts_sentence(line):
                flush()

        current.append(line)

    flush()
    return "\n\n".join(paragraphs)


class TextCleaner:
    """Clean pages batch by batch, remembering the running heads seen.

    Running heads change from chapter to chapter, so the set grows as
    more of the book is parsed: a header that repeats in the current
    batch is dropped from it, and a header seen in an earlier batch stays
    dropped even when the current batch is too small to reveal it.
    """

    def __init__(self):
        self.heads = set()

    def clean(self, raw_pages):
        prepared = [_prepare(page) for page in raw_pages]
        self.heads |= running_heads(prepared)
        return [reflow([line for line in lines
                        if not _is_furniture(line, self.heads)])
                for lines in prepared]


def clean_pages(raw_pages):
    """Turn raw extracted pages into readable pages of plain text."""

    return TextCleaner().clean(raw_pages)


def _batches(total, size):
    """Page ranges for extraction, with a short tail folded into the last.

    A final batch of one or two pages cannot show a repeating header, so
    it joins the batch before it instead of being cleaned blind.
    """

    starts = list(range(0, total, size))
    if len(starts) > 1 and total - starts[-1] < 4:
        starts.pop()
    return [(start, starts[index + 1] if index + 1 < len(starts) else total)
            for index, start in enumerate(starts)]


# ---------------- Cleaning Markdown ---------------- #

_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPHASIS = re.compile(r"(\*\*|__|\*|`{1,3})")
_RULE = re.compile(r"^\s*(?:[-*_])\s*(?:[-*_]\s*){2,}$", re.MULTILINE)


def markdown_body(text):
    """Strip the conversion's front matter and the loudest Markdown marks."""

    body = _FRONTMATTER.sub("", text.replace("\r\n", "\n"))
    body = _RULE.sub("", body)
    body = _HEADING.sub("", body)
    body = _LINK.sub(r"\1", body)
    body = _EMPHASIS.sub("", body)
    body = _SPACES.sub(" ", body)
    return body.strip()


def split_markdown(text, page_chars=MARKDOWN_PAGE_CHARS):
    """Cut Markdown prose into reading pages at paragraph boundaries."""

    paragraphs = [block.strip() for block in re.split(r"\n\s*\n", text)
                  if block.strip()]
    if not paragraphs:
        return ("",)

    pages = []
    current = []
    size = 0
    for paragraph in paragraphs:
        if current and size + len(paragraph) > page_chars:
            pages.append("\n\n".join(current))
            current, size = [], 0
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        pages.append("\n\n".join(current))
    return tuple(pages)


def markdown_pages(source):
    try:
        text = source.path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = source.path.read_text(encoding="utf-8", errors="replace")
    return split_markdown(markdown_body(text))


# ---------------- PDF extraction ---------------- #


def _reader(source):
    from pypdf import PdfReader  # imported here so helpers stay importable

    return PdfReader(str(source.path))


def page_count(source):
    """How many pages the source has, without extracting any text."""

    if source.kind == "markdown":
        return len(markdown_pages(source))
    return len(_reader(source).pages)


def extract_chunks(source, chunk_pages=CHUNK_PAGES):
    """Yield cleaned pages in batches, so the reader can start early.

    A page that fails to parse becomes an empty page instead of killing
    the whole book.
    """

    if source.kind == "markdown":
        pages = list(markdown_pages(source))
        for start in range(0, len(pages), chunk_pages):
            yield pages[start:start + chunk_pages]
        return

    reader = _reader(source)
    cleaner = TextCleaner()
    for start, stop in _batches(len(reader.pages), chunk_pages):
        raw = []
        for index in range(start, stop):
            try:
                raw.append(reader.pages[index].extract_text() or "")
            except Exception:  # a broken page should not lose the book
                raw.append("")
        yield cleaner.clean(raw)


def extract(book, folder=BOOKS_FOLDER):
    """Extract a whole book synchronously. Used by tests and small tools."""

    source = source_for(book, folder)
    if source is None:
        return None
    pages = []
    for chunk in extract_chunks(source):
        pages.extend(chunk)
    return BookText(tuple(pages), source.kind, source.path.name)


# ---------------- Cache ---------------- #


def cache_paths(book, folder=CACHE_FOLDER):
    folder = Path(folder)
    return folder / f"{book.key}.txt", folder / f"{book.key}.json"


def read_cache(book, source, folder=CACHE_FOLDER):
    """Return the cached text, or ``None`` if it is missing or stale."""

    text_path, meta_path = cache_paths(book, folder)
    if not (text_path.is_file() and meta_path.is_file()):
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if meta.get("size") != source.size:
        return None
    if abs(float(meta.get("modified", 0)) - source.modified) > 0.001:
        return None

    try:
        text = text_path.read_text(encoding="utf-8")
    except OSError:
        return None

    pages = tuple(text.split(PAGE_BREAK))
    if len(pages) != meta.get("pages"):
        return None
    return BookText(pages, meta.get("kind", source.kind),
                    meta.get("source_name", source.path.name), True)


def write_cache(book, source, pages, folder=CACHE_FOLDER):
    """Store extracted pages. Returns ``True`` when the cache was written."""

    text_path, meta_path = cache_paths(book, folder)
    try:
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(PAGE_BREAK.join(pages), encoding="utf-8")
        meta_path.write_text(json.dumps({
            "source_name": source.path.name,
            "kind": source.kind,
            "size": source.size,
            "modified": source.modified,
            "pages": len(pages),
        }, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def clear_cache(folder=CACHE_FOLDER):
    """Delete cached text. Returns the number of files removed."""

    folder = Path(folder)
    if not folder.is_dir():
        return 0
    removed = 0
    for path in folder.glob("*"):
        if path.suffix in (".txt", ".json"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed
