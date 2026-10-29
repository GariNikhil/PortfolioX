"""Tests for the PNB mPassbook statement importer (PDF text parsing)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import (
    find_account_by_name,
    get_accounts,
    get_bank_transactions,
)
from database.schema import ensure_schema
from importers.common import ImportFileError
from importers.pnb_statement import import_pnb_statement, parse_pnb_pages
from security.vault import PasswordRequiredError

# Fixture shaped like the real statement (referance/stock/bank
# accounts&statements/PNBONE_mPassbook_...pdf): NEWEST FIRST rows,
# remarks wrapped mid-token, and the last page's disclaimer text sitting
# before older rows.
#
# Chronological chain: opening 550.00; 50 DR -> 500.00; 500 CR ->
# 1000.00; 100 DR -> 900.00 (the closing balance = newest row's).
_PAGES = ["""
  
  
Branch Details 
  
Branch Name:        DEMOCITY (A.P.) 
IFSC Code:            PUNB0608900 
  
Customer Details: 
  
Customer Name:      DEMO INVESTOR 
  
Statement of Account:0000000000000001 For Period: 18/08/2025 to 18/10/2025 
  
Date Instrument ID Amount Type Balance Remarks
05/10/2025 100.00 DR 900.00 UPI/DR/111111111111/TES
TER/YESB/tester@ybl/P
04/10/2025 500.00 CR 1,000.00 UPI/CR/222222222222/SOU
RCE/SBIN/source@ybl/P
""", """
***Generated through PNB ONE***  
● Unless constituent notifies the bank immediately of any discrepancy found by him in his statement of Account,it will be
taken that he has found the account correct.
● Computer genertaed entries shown in the statement of account do not require any authentication / initial from the bank
official. please do not accept any manual entry in your computer generated statement of account.
03/10/2025 50.00 DR 500.00 UPI WDR 333333333333
02/10/2025 25.00 CR 550.00 UPI/CR/444444444444/GIV
ER/SBIN/giver@ybl/P
"""]


class PnbParserTests(unittest.TestCase):
    def test_parses_rows_chronologically_with_signs(self):
        rows, failures, meta = parse_pnb_pages(_PAGES)

        self.assertEqual(failures, [])
        self.assertEqual(len(rows), 4)

        # Reversed to chronological order.
        dates = [row["txn_date"] for row in rows]
        self.assertEqual(dates, [
            "2025-10-02", "2025-10-03", "2025-10-04", "2025-10-05",
        ])
        self.assertEqual([row["amount"] for row in rows],
                         [25.0, -50.0, 500.0, -100.0])
        self.assertEqual([row["balance"] for row in rows],
                         [550.0, 500.0, 1000.0, 900.0])

        # Mid-token remark wrap rejoined without a space (UPI id intact).
        self.assertEqual(
            rows[0]["description"],
            "UPI/CR/444444444444/GIVER/SBIN/giver@ybl/P",
        )
        self.assertEqual(rows[1]["description"], "UPI WDR 333333333333")

        # Closing balance = the NEWEST row's balance.
        self.assertEqual(meta["closing_balance"], 900.0)
        self.assertEqual(meta["details"], {
            "holder_name": "Demo Investor",
            "account_number": "0000000000000001",
        })

    def test_footer_text_never_pollutes_remarks(self):
        rows, _failures, _meta = parse_pnb_pages(_PAGES)

        for row in rows:
            self.assertNotIn("Generated", row["description"])
            self.assertNotIn("constituent", row["description"])
            self.assertNotIn("genertaed", row["description"])

    def test_broken_balance_chain_is_reported_but_rows_imported(self):
        pages = ["""
Customer Name:      SOMEONE 
Statement of Account:6000000000000001 For Period: 01/10/2025 to 05/10/2025 
Date Instrument ID Amount Type Balance Remarks
05/10/2025 100.00 DR 900.00 UPI/DR/1/A
04/10/2025 500.00 CR 1,050.00 UPI/CR/2/B
"""]

        rows, failures, _meta = parse_pnb_pages(pages)

        # 500.00 CR should land on 1000.00, not 1050.00: reported, but
        # the explicit DR/CR rows are still stored.
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(failures), 1)
        self.assertIn("does not reconcile", failures[0].reason)

    def test_no_rows_raises(self):
        with self.assertRaises(ImportFileError):
            parse_pnb_pages(["***Generated through PNB ONE***", "no rows"])


class PnbImportFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "p.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)

    def _import(self):
        with patch.object(pnb_module(), "read_pdf_pages", return_value=_PAGES):
            return import_pnb_statement("PNBONE_mPassbook.pdf")

    def test_first_import_creates_the_bank_account(self):
        result = self._import()

        self.assertEqual(result.imported, 4)
        self.assertIn("Created account 'PNB Bank' (PERSONAL)", result.notes)

        account = find_account_by_name("PNB Bank")
        self.assertEqual(account["kind"], "PERSONAL")
        self.assertEqual(account["account_number"], "0000000000000001")
        self.assertEqual(account["holder_name"], "Demo Investor")
        # Raw account rows carry paise.
        self.assertEqual(account["current_balance"], 90000)
        self.assertEqual(
            len(get_bank_transactions(account_id=account["id"])), 4,
        )

    def test_reimport_detects_the_account_and_deduplicates(self):
        self._import()
        result = self._import()

        self.assertEqual(result.imported, 0)
        self.assertEqual(result.duplicates, 4)
        self.assertEqual(
            len([a for a in get_accounts() if a["name"] == "PNB Bank"]), 1,
        )

    def test_missing_vault_password_raises_password_required(self):
        with patch.object(pnb_module(), "read_pdf_pages",
                          side_effect=PasswordRequiredError("need password")):
            with self.assertRaises(PasswordRequiredError):
                import_pnb_statement("PNBONE_mPassbook.pdf")


def pnb_module():
    import importers.pnb_statement as module
    return module


if __name__ == "__main__":
    unittest.main()
