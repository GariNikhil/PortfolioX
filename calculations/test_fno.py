"""Tests for F&O symbol normalization across broker sources."""

import unittest

from calculations.fno import canonical_symbol, normalize_fno_symbol


class NormalizeFnoTests(unittest.TestCase):
    def test_spaced_dd_mmm_yyyy(self):
        self.assertEqual(
            normalize_fno_symbol("BANKNIFTY 45500 PE 27 JUL 2023"),
            "BANKNIFTY 45500 PE 2023-07-27",
        )

    def test_nospace_compact_form(self):
        self.assertEqual(
            normalize_fno_symbol("BANKNIFTY45500PE27Jul2023"),
            "BANKNIFTY 45500 PE 2023-07-27",
        )

    def test_already_iso_stays_canonical(self):
        self.assertEqual(
            normalize_fno_symbol("BANKNIFTY 40500 PE 2023-03-09"),
            "BANKNIFTY 40500 PE 2023-03-09",
        )

    def test_iifl_style_call(self):
        self.assertEqual(
            normalize_fno_symbol("NIFTY 19150 PE 03 AUG 2023"),
            "NIFTY 19150 PE 2023-08-03",
        )

    def test_all_sources_converge(self):
        shapes = [
            "BANKNIFTY 45500 PE 27 JUL 2023",
            "BANKNIFTY45500PE27Jul2023",
            "BANKNIFTY45500PE2023-07-27",
            "banknifty 45500 pe 27 jul 2023",
        ]
        canonical = {normalize_fno_symbol(shape) for shape in shapes}

        self.assertEqual(canonical, {"BANKNIFTY 45500 PE 2023-07-27"})

    def test_nospace_iso_form(self):
        self.assertEqual(
            normalize_fno_symbol("BANKNIFTY45500PE2023-07-27"),
            "BANKNIFTY 45500 PE 2023-07-27",
        )

    def test_idempotent(self):
        once = normalize_fno_symbol("BANKNIFTY 45500 PE 27 JUL 2023")

        self.assertEqual(normalize_fno_symbol(once), once)

    def test_strike_decimals_kept_but_clean_zero(self):
        self.assertEqual(
            normalize_fno_symbol("NIFTY 19150.5 CE 03 AUG 2023"),
            "NIFTY 19150.5 CE 2023-08-03",
        )
        self.assertEqual(
            normalize_fno_symbol("NIFTY 19150.0 CE 03 AUG 2023"),
            "NIFTY 19150 CE 2023-08-03",
        )

    def test_invalid_date_returns_none(self):
        self.assertIsNone(normalize_fno_symbol("BANKNIFTY 45500 PE 32 JUL 2023"))
        self.assertIsNone(normalize_fno_symbol("BANKNIFTY 45500 PE 2023-13-01"))

    def test_unknown_month_returns_none(self):
        self.assertIsNone(normalize_fno_symbol("BANKNIFTY 45500 PE 27 XYZ 2023"))


class CanonicalSymbolTests(unittest.TestCase):
    def test_non_fno_passes_through_unchanged(self):
        for symbol in ("RELIANCE", "COAL INDIA LTD.", "RELIANCE POWER L", "NTPC"):
            self.assertEqual(canonical_symbol(symbol), symbol)

    def test_unparseable_fno_like_text_passes_through(self):
        self.assertEqual(canonical_symbol("BANKNIFTY PE 2023"), "BANKNIFTY PE 2023")

    def test_none_and_empty_pass_through(self):
        self.assertEqual(canonical_symbol(None), None)
        self.assertEqual(canonical_symbol(""), "")

    def test_fno_is_normalized(self):
        self.assertEqual(
            canonical_symbol("BANKNIFTY45500PE27Jul2023"),
            "BANKNIFTY 45500 PE 2023-07-27",
        )


if __name__ == "__main__":
    unittest.main()
