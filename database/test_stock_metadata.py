"""Tests for stock metadata storage and the metadata-driven splits."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import (
    find_stock_metadata,
    get_stock_metadata,
    set_stock_metadata,
)
from database.schema import SCHEMA_VERSION, ensure_schema
from calculations.allocation import (
    market_cap_allocation,
    market_cap_category,
    sector_allocation,
)


class StockMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "p.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)

    def test_set_and_get_roundtrip(self):
        set_stock_metadata("PUNJAB NATIONAL BANK",
                           sector="Financial Services",
                           market_cap=1_15_000 * 10**7)
        set_stock_metadata("GROWWAMC - GROWWGOLD", sector="ETF",
                           market_cap=None, source="local_classification")

        rows = {row["symbol"]: row for row in get_stock_metadata()}
        self.assertEqual(rows["PUNJAB NATIONAL BANK"]["sector"],
                         "Financial Services")
        self.assertEqual(rows["PUNJAB NATIONAL BANK"]["market_cap"],
                         1_15_000 * 10**7)
        self.assertEqual(rows["GROWWAMC - GROWWGOLD"]["sector"], "ETF")
        self.assertIsNone(rows["GROWWAMC - GROWWGOLD"]["market_cap"])
        self.assertEqual(rows["GROWWAMC - GROWWGOLD"]["source"],
                         "local_classification")

    def test_upsert_overwrites(self):
        set_stock_metadata("PNB", sector="Old", market_cap=1)
        set_stock_metadata("PNB", sector="Financial Services",
                           market_cap=1_15_000 * 10**7)

        rows = get_stock_metadata()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sector"], "Financial Services")
        self.assertEqual(rows[0]["market_cap"], 1_15_000 * 10**7)

    def test_find_one_symbol(self):
        self.assertIsNone(find_stock_metadata("PNB"))
        set_stock_metadata("PNB", sector="Financial Services", market_cap=1)
        self.assertEqual(find_stock_metadata("pnb")["sector"],
                         "Financial Services")  # case-insensitive lookup

    def test_requires_symbol(self):
        with self.assertRaises(ValueError):
            set_stock_metadata("   ", sector="X")

    def test_v8_schema_version(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 8)


class MarketCapCategoryTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(market_cap_category(1_00_000 * 10**7), "Large Cap")
        self.assertEqual(market_cap_category(25_000 * 10**7), "Mid Cap")
        self.assertEqual(market_cap_category(24_999 * 10**7), "Small Cap")


class MetadataSplitTests(unittest.TestCase):
    HOLDINGS = [
        {"symbol": "RELIANCE", "invested_amount": 500.0},
        {"symbol": "PNB", "invested_amount": 100.0},
        {"symbol": "GROWWAMC - GROWWGOLD", "invested_amount": 50.0},
        {"symbol": "SBI ELSS TAX SAVER FUND DIRECT GROWTH",
         "invested_amount": 50.0},
        {"symbol": "BANKNIFTY 45000 CE 2023-07-13", "invested_amount": 0.0},
        {"symbol": "MYSTERY WIDGETS", "invested_amount": 200.0},
    ]

    def _metadata(self):
        return {
            "RELIANCE": {"sector": "Energy",
                         "market_cap": 19_00_000 * 10**7},
            "PNB": {"sector": "Financial Services",
                    "market_cap": 1_15_000 * 10**7},
            "GROWWAMC - GROWWGOLD": {"sector": "ETF", "market_cap": None},
            "SBI ELSS TAX SAVER FUND DIRECT GROWTH": {
                "sector": "Mutual Fund", "market_cap": None},
        }

    def test_sector_split(self):
        split = sector_allocation(self.HOLDINGS, self._metadata())
        self.assertEqual(split, [
            ("Energy", 500.0),
            ("Unclassified", 200.0),
            ("Financial Services", 100.0),
            ("ETF", 50.0),
            ("Mutual Fund", 50.0),
        ])

    def test_cap_split(self):
        split = market_cap_allocation(self.HOLDINGS, self._metadata())
        self.assertEqual(split, [
            ("Large Cap", 600.0),      # Reliance + PNB
            ("Unclassified", 200.0),   # no metadata row
            ("ETF", 50.0),
            ("Mutual Fund", 50.0),
        ])

    def test_small_and_mid_cap(self):
        holdings = [
            {"symbol": "A", "invested_amount": 10.0},
            {"symbol": "B", "invested_amount": 20.0},
        ]
        metadata = {
            "A": {"sector": "Energy", "market_cap": 30_000 * 10**7},
            "B": {"sector": "Energy", "market_cap": 5_000 * 10**7},
        }
        self.assertEqual(market_cap_allocation(holdings, metadata), [
            ("Small Cap", 20.0),
            ("Mid Cap", 10.0),
        ])


if __name__ == "__main__":
    unittest.main()
