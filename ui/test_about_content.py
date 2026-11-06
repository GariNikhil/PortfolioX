"""Tests for the About me profile content (no Tk, no database required).

The page renders whatever ``profile_rows()`` returns, so these tests pin
down that contract: which fields appear, in what order, and how blank or
half-filled values are dropped.
"""

import unittest

from ui import about_content
from ui.about_content import profile_rows


class ProfileRowsTests(unittest.TestCase):
    def test_all_fields_keep_display_order(self):
        rows = profile_rows(
            name="Demo Investor",
            bio="Long-term equity investor.",
            email="nikhil@example.com",
            links=(("GitHub", "https://github.com/nikhil"),),
        )

        self.assertEqual(
            [kind for kind, _value in rows], ["name", "bio", "email", "links"]
        )

    def test_blank_fields_are_skipped(self):
        rows = profile_rows(name="Demo Investor", bio="", email="", links=())

        self.assertEqual(rows, [("name", "Demo Investor")])

    def test_whitespace_counts_as_blank(self):
        rows = profile_rows(
            name="  Demo Investor  ", bio="   ", email="\n\t", links=()
        )

        self.assertEqual(rows, [("name", "Demo Investor")])

    def test_values_are_trimmed(self):
        rows = profile_rows(
            name=" Demo Investor ",
            bio="  Investor.  ",
            email="  nikhil@example.com  ",
            links=(),
        )

        self.assertEqual(
            rows,
            [
                ("name", "Demo Investor"),
                ("bio", "Investor."),
                ("email", "nikhil@example.com"),
            ],
        )

    def test_links_need_both_a_label_and_a_url(self):
        rows = profile_rows(
            name="Demo Investor",
            email="",
            links=(
                ("GitHub", "https://github.com/nikhil"),
                ("LinkedIn", ""),
                ("", "https://x.com/nikhil"),
                ("  ", "  "),
            ),
        )

        self.assertEqual(
            rows,
            [
                ("name", "Demo Investor"),
                ("links", (("GitHub", "https://github.com/nikhil"),)),
            ],
        )

    def test_links_are_trimmed_and_stay_in_order(self):
        rows = profile_rows(
            name="",
            email="",
            links=(
                (" GitHub ", " https://github.com/nikhil "),
                ("LinkedIn", " https://www.linkedin.com/in/nikhil "),
            ),
        )

        self.assertEqual(
            rows,
            [
                (
                    "links",
                    (
                        ("GitHub", "https://github.com/nikhil"),
                        ("LinkedIn", "https://www.linkedin.com/in/nikhil"),
                    ),
                )
            ],
        )

    def test_empty_profile_produces_no_rows(self):
        self.assertEqual(profile_rows(name="", bio="", email="", links=()), [])

    def test_none_values_are_treated_as_blank(self):
        self.assertEqual(profile_rows(name=None, bio=None, email=None, links=None), [])

    def test_shipped_profile_shows_the_name_first(self):
        rows = profile_rows()

        self.assertTrue(rows)
        self.assertEqual(rows[0], ("name", about_content.NAME.strip()))
        self.assertTrue(about_content.NAME.strip())

    def test_omitted_fields_fall_back_to_the_shipped_profile(self):
        """The page calls this with no arguments, so defaults are the profile."""

        rows = profile_rows(name="Someone Else")

        self.assertEqual(rows[0], ("name", "Someone Else"))
        self.assertEqual(dict(profile_rows())["email"], about_content.EMAIL.strip())


if __name__ == "__main__":
    unittest.main()
