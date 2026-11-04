"""Tests for the book shelf: cleaning, Markdown, caching, extraction.

The parsing rules are the part that decides whether a book reads well
inside the app, so they are pinned here with synthetic pages. The tests
that read the real shelf skip when ``referance/books`` is absent — the
folder is personal material and is not part of the source tree.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from books import library


def fake_book(key="sample", file_name="Sample.pdf"):
    return SimpleNamespace(key=key, file_name=file_name)


class SourceTests(unittest.TestCase):
    """Which file a book is read from."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_prefers_the_markdown_conversion(self):
        (self.folder / "Sample.pdf").write_bytes(b"%PDF-1.4")
        (self.folder / "Sample.md").write_text("# Notes", encoding="utf-8")

        source = library.source_for(fake_book(), self.folder)

        self.assertEqual(source.kind, "markdown")
        self.assertEqual(source.path.suffix, ".md")

    def test_falls_back_to_the_pdf(self):
        (self.folder / "Sample.pdf").write_bytes(b"%PDF-1.4")

        source = library.source_for(fake_book(), self.folder)

        self.assertEqual(source.kind, "pdf")
        self.assertEqual(source.path.name, "Sample.pdf")

    def test_missing_book_has_no_source(self):
        self.assertIsNone(library.source_for(fake_book(), self.folder))

    def test_source_remembers_size_and_time_for_the_cache(self):
        path = self.folder / "Sample.pdf"
        path.write_bytes(b"%PDF-1.4")

        source = library.source_for(fake_book(), self.folder)

        self.assertEqual(source.size, path.stat().st_size)
        self.assertGreater(source.modified, 0)


class ReflowTests(unittest.TestCase):
    """Joining hard-wrapped PDF lines back into paragraphs."""

    def test_joins_wrapped_lines(self):
        text = library.reflow([
            "The quick brown fox jumps over the",
            "lazy dog and keeps running until dusk.",
        ])

        self.assertEqual(
            text,
            "The quick brown fox jumps over the lazy dog and keeps running "
            "until dusk.",
        )

    def test_sews_a_word_broken_on_a_hyphen(self):
        text = library.reflow([
            "Weekly rule breakouts use the same num-",
            "bers translated into 2, 4, and 8 weeks.",
        ])

        self.assertIn("same numbers translated", text)
        self.assertNotIn("num-", text)

    def test_keeps_the_hyphen_before_a_capital(self):
        text = library.reflow(["It was a well-", "Known result."])

        self.assertIn("well-Known", text)

    def test_starts_a_paragraph_after_a_finished_sentence(self):
        text = library.reflow([
            "He said the market was closed.",
            "Then he left the room.",
        ])

        self.assertEqual(
            text, "He said the market was closed.\n\nThen he left the room."
        )

    def test_a_short_line_ends_a_paragraph(self):
        filler = "This line is long enough to set the measure for the page."
        text = library.reflow([filler, filler, "The end.", "Next section"])

        self.assertIn("The end.\n\nNext section", text)

    def test_bullets_keep_their_own_line(self):
        text = library.reflow([
            "Before the list.",
            "• first point",
            "• second point",
        ])

        self.assertEqual(
            text, "Before the list.\n\n• first point\n\n• second point"
        )

    def test_empty_input_gives_empty_text(self):
        self.assertEqual(library.reflow([]), "")
        self.assertEqual(library.reflow(["", "   "]), "")


class CleaningTests(unittest.TestCase):
    """What a page loses: page numbers, running heads, ligatures."""

    def test_page_numbers_and_roman_numerals_are_dropped(self):
        page = library.clean_pages([[
            "The chapter opens here.",
            "32",
            "iv",
            "Page 4 of 12",
        ]])[0]

        self.assertIn("The chapter opens here.", page)
        self.assertNotIn("32", page)
        self.assertNotIn("Page 4 of 12", page)

    def test_ordinary_words_are_not_mistaken_for_page_numbers(self):
        page = library.clean_pages([["mix", "civil", "mild"]])[0]

        for word in ("mix", "civil", "mild"):
            self.assertIn(word, page)

    def test_running_heads_are_dropped_from_every_page(self):
        pages = [[
            "The Warren Buffett Way",
            f"Body text for page {number} that is unique to this page.",
            str(number),
        ] for number in range(1, 8)]

        cleaned = library.clean_pages(pages)

        for page in cleaned:
            self.assertNotIn("The Warren Buffett Way", page)
            self.assertIn("Body text for page", page)

    def test_running_heads_survive_a_page_number_on_either_side(self):
        pages = [[
            header,
            "A paragraph that only appears on this page, long enough to keep.",
        ] for header in (
            "352 Chapter 14", "Time Cycles 353", "354 Chapter 14",
            "Time Cycles 355", "356 Chapter 14", "Time Cycles 357",
        )]

        cleaned = library.clean_pages(pages)

        for page in cleaned:
            self.assertNotIn("Chapter 14", page)
            self.assertNotIn("Time Cycles", page)

    def test_ligatures_and_soft_hyphens_are_repaired(self):
        page = library.clean_pages([[
            "The body \ufb01ghts in\ufb02ammation, and a\u00adgencies agree.",
        ]])[0]

        self.assertIn("fights inflammation", page)
        self.assertIn("agencies agree", page)

    def test_cleaner_carries_heads_between_batches(self):
        cleaner = library.TextCleaner()
        first = cleaner.clean([[
            "A Book Title", "First batch page, long enough to be body text."
        ] for _ in range(5)])
        second = cleaner.clean([[
            "A Book Title", "Second batch page, long enough to be body text."
        ]])

        self.assertTrue(first)
        self.assertNotIn("A Book Title", second[0])

    def test_short_tail_joins_the_previous_batch(self):
        batches = library._batches(23, 10)

        self.assertEqual(batches[0], (0, 10))
        self.assertEqual(batches[-1], (10, 23))
        self.assertEqual(len(batches), 2)

    def test_batches_cover_every_page_once(self):
        covered = []
        for start, stop in library._batches(47, 10):
            covered.extend(range(start, stop))

        self.assertEqual(covered, list(range(47)))


class MarkdownTests(unittest.TestCase):

    def test_body_drops_front_matter_and_marks(self):
        text = (
            "---\n"
            'source: "[[Option_Trading_Strategies.pdf]]"\n'
            "pages_converted: 58/58\n"
            "---\n\n"
            "## OPTION TRADING STRATEGIES\n\n"
            "### Section\n\n"
            "Buy a **call** when you see [the setup](https://example.com).\n"
        )

        body = library.markdown_body(text)

        self.assertNotIn("pages_converted", body)
        self.assertNotIn("##", body)
        self.assertNotIn("**", body)
        self.assertNotIn("https://example.com", body)
        self.assertIn("OPTION TRADING STRATEGIES", body)
        self.assertIn("Buy a call when you see the setup.", body)

    def test_split_cuts_at_paragraphs(self):
        paragraph = "A paragraph of prose that fills some of the page. " * 6
        pages = library.split_markdown("\n\n".join([paragraph] * 5),
                                       page_chars=1200)

        self.assertGreater(len(pages), 1)
        self.assertTrue(all(page.strip() for page in pages))
        for page in pages:
            self.assertTrue(page.startswith("A paragraph of prose"))

    def test_empty_markdown_still_has_one_page(self):
        self.assertEqual(library.split_markdown("   "), ("",))


class CacheTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        self.shelf = self.root / "books"
        self.shelf.mkdir()
        self.cache = self.root / "cache"
        self.path = self.shelf / "Sample.pdf"
        self.path.write_bytes(b"%PDF-1.4 sample")

        self.book = fake_book()
        self.source = library.source_for(self.book, self.shelf)

    def test_round_trip(self):
        pages = ("First page of the book.", "Second page.")

        self.assertTrue(library.write_cache(self.book, self.source, pages,
                                           self.cache))
        loaded = library.read_cache(self.book, self.source, self.cache)

        self.assertEqual(loaded.pages, pages)
        self.assertTrue(loaded.from_cache)
        self.assertEqual(loaded.page_count, 2)

    def test_missing_cache_reads_as_none(self):
        self.assertIsNone(library.read_cache(self.book, self.source,
                                             self.root / "absent"))

    def test_changed_file_invalidates_the_cache(self):
        library.write_cache(self.book, self.source, ("Old text.",), self.cache)
        self.path.write_bytes(b"%PDF-1.4 sample with more content")
        fresh = library.source_for(self.book, self.shelf)

        self.assertIsNone(library.read_cache(self.book, fresh, self.cache))

    def test_corrupt_metadata_is_ignored(self):
        library.write_cache(self.book, self.source, ("Text.",), self.cache)
        _, meta_path = library.cache_paths(self.book, self.cache)
        meta_path.write_text("not json", encoding="utf-8")

        self.assertIsNone(library.read_cache(self.book, self.source, self.cache))

    def test_clear_cache_removes_extracted_text(self):
        library.write_cache(self.book, self.source, ("Text.",), self.cache)

        self.assertEqual(library.clear_cache(self.cache), 2)
        self.assertIsNone(library.read_cache(self.book, self.source, self.cache))


class RealShelfTests(unittest.TestCase):
    """Read the actual shelf when it is present on this computer."""

    def setUp(self):
        if not library.BOOKS_FOLDER.is_dir():
            self.skipTest("referance/books is not present")

    def test_every_book_resolves_to_a_file(self):
        from ui.learn_content import BOOKS

        for book in BOOKS:
            with self.subTest(book=book.key):
                self.assertIsNotNone(
                    library.source_for(book),
                    f"{book.key}: {book.file_name} is missing",
                )

    def test_a_markdown_book_extracts_into_pages(self):
        from ui.learn_content import BOOKS

        book = next((entry for entry in BOOKS
                     if library.source_for(entry)
                     and library.source_for(entry).kind == "markdown"), None)
        if book is None:
            self.skipTest("no Markdown conversion on the shelf")

        text = library.extract(book)

        self.assertGreater(text.page_count, 3)
        self.assertGreater(text.characters, 2000)
        self.assertNotIn("pages_converted", text.pages[0])
        self.assertTrue(all(page.strip() for page in text.pages))

    def test_chunks_add_up_to_the_page_count(self):
        from ui.learn_content import BOOKS

        book = next(entry for entry in BOOKS
                    if library.source_for(entry)
                    and library.source_for(entry).kind == "markdown")
        source = library.source_for(book)

        chunks = list(library.extract_chunks(source, chunk_pages=4))
        pages = [page for chunk in chunks for page in chunk]

        self.assertEqual(len(pages), library.page_count(source))
        self.assertGreater(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
