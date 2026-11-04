"""Tests for the offline Learn content (no Tk, no database required).

The content module is plain data, so these tests check the shape of the
library: unique keys, fields that are actually filled in, tracks and
levels that exist, and citations that point at real books. One guarded
test confirms every PDF in ``referance/books`` is represented; it skips
when the local (gitignored) folder is not present.
"""

import unittest
from pathlib import Path

from ui.learn_content import (
    BOOKS,
    BOOK_BY_KEY,
    EXTRA_REFERENCES,
    LEVELS,
    LESSONS,
    PLANNING_PHASES,
    PLAYBOOK,
    TRACKS,
    filter_books,
    source_titles,
)

BOOKS_FOLDER = Path(__file__).resolve().parent.parent / "referance" / "books"


class BookLibraryTests(unittest.TestCase):
    def test_every_book_has_a_unique_key_and_title(self):
        keys = [book.key for book in BOOKS]
        titles = [book.title for book in BOOKS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(titles), len(set(titles)))

    def test_there_are_books_to_show(self):
        self.assertGreaterEqual(len(BOOKS), 10)

    def test_required_text_fields_are_filled(self):
        for book in BOOKS:
            with self.subTest(book=book.key):
                for field in (
                    "key",
                    "title",
                    "short_title",
                    "author",
                    "year",
                    "track",
                    "level",
                    "file_name",
                    "thesis",
                ):
                    value = getattr(book, field)
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip(), f"{book.key}.{field} is empty")
                self.assertGreater(len(book.thesis), 40)

    def test_notes_are_substantial(self):
        for book in BOOKS:
            with self.subTest(book=book.key):
                self.assertGreaterEqual(len(book.ideas), 3)
                self.assertGreaterEqual(len(book.tricks), 2)
                self.assertGreaterEqual(len(book.planning), 1)
                for note in book.ideas + book.tricks + book.planning:
                    self.assertIsInstance(note, str)
                    self.assertGreater(len(note.strip()), 20)

    def test_track_and_level_are_known(self):
        track_keys = {track.key for track in TRACKS}
        for book in BOOKS:
            with self.subTest(book=book.key):
                self.assertIn(book.track, track_keys)
                self.assertIn(book.level, LEVELS)

    def test_every_track_has_at_least_one_book(self):
        for track in TRACKS:
            with self.subTest(track=track.key):
                self.assertTrue(track.title.strip())
                self.assertTrue(track.blurb.strip())
                self.assertTrue(filter_books(track=track.key))

    def test_lookup_index_matches_the_shelf(self):
        self.assertEqual(set(BOOK_BY_KEY), {book.key for book in BOOKS})


class PlaybookTests(unittest.TestCase):
    def test_entries_are_unique_and_filled(self):
        keys = [entry.key for entry in PLAYBOOK]
        self.assertEqual(len(keys), len(set(keys)))
        for entry in PLAYBOOK:
            with self.subTest(entry=entry.key):
                self.assertTrue(entry.title.strip())
                self.assertTrue(entry.principle.strip())
                self.assertGreaterEqual(len(entry.rules), 3)
                self.assertGreaterEqual(len(entry.sources), 1)

    def test_sources_point_at_real_books(self):
        for entry in PLAYBOOK:
            for key in entry.sources:
                with self.subTest(entry=entry.key, source=key):
                    self.assertIn(key, BOOK_BY_KEY)


class PlanningTests(unittest.TestCase):
    def test_phases_are_unique_and_filled(self):
        keys = [phase.key for phase in PLANNING_PHASES]
        self.assertEqual(len(keys), len(set(keys)))
        for phase in PLANNING_PHASES:
            with self.subTest(phase=phase.key):
                self.assertTrue(phase.title.strip())
                self.assertTrue(phase.summary.strip())
                self.assertGreaterEqual(len(phase.actions), 3)
                self.assertGreaterEqual(len(phase.sources), 1)

    def test_sources_point_at_real_books(self):
        for phase in PLANNING_PHASES:
            for key in phase.sources:
                with self.subTest(phase=phase.key, source=key):
                    self.assertIn(key, BOOK_BY_KEY)


class LessonTests(unittest.TestCase):
    def test_lessons_have_a_heading_and_body(self):
        self.assertTrue(LESSONS)
        for heading, body in LESSONS:
            with self.subTest(lesson=heading):
                self.assertGreater(len(heading.strip()), 5)
                self.assertGreater(len(body.strip()), 40)


class SourceTitleTests(unittest.TestCase):
    def test_short_titles_are_joined(self):
        self.assertEqual(
            source_titles(("random-walk", "buffett-way")),
            "A Random Walk Down Wall Street, The Warren Buffett Way",
        )

    def test_single_source(self):
        self.assertEqual(source_titles(("murphy",)), "Technical Analysis of the Financial Markets")


class FilterBooksTests(unittest.TestCase):
    def test_no_query_returns_the_whole_shelf(self):
        self.assertEqual(filter_books(), BOOKS)

    def test_track_filter(self):
        options = filter_books(track="options")
        self.assertTrue(options)
        self.assertTrue(all(book.track == "options" for book in options))

    def test_search_matches_title_case_insensitively(self):
        matches = filter_books("buffett")
        self.assertIn("buffett-way", {book.key for book in matches})

    def test_search_reaches_notes_not_just_titles(self):
        matches = filter_books("margin of safety")
        self.assertIn("buffett-way", {book.key for book in matches})

    def test_search_and_track_combine(self):
        matches = filter_books("stop", track="technical")
        self.assertTrue(matches)
        for book in matches:
            self.assertEqual(book.track, "technical")

    def test_unknown_query_is_empty(self):
        self.assertEqual(filter_books("no-such-topic-anywhere"), ())

    def test_whitespace_query_is_ignored(self):
        self.assertEqual(filter_books("   "), BOOKS)


class ShelfCoverageTests(unittest.TestCase):
    """Every PDF in the local book folder must have a digest."""

    def test_every_pdf_is_covered(self):
        if not BOOKS_FOLDER.is_dir():
            self.skipTest("referance/books is not present")

        pdfs = {path.name for path in BOOKS_FOLDER.glob("*.pdf")}
        self.assertTrue(pdfs, "no PDFs found in referance/books")
        covered = {book.file_name for book in BOOKS}
        self.assertEqual(pdfs - covered, set(), "books on the shelf without a digest")

    def test_extra_references_exist(self):
        for file_name, description in EXTRA_REFERENCES:
            with self.subTest(file=file_name):
                self.assertTrue(file_name.strip())
                self.assertTrue(description.strip())


if __name__ == "__main__":
    unittest.main()
